"""Docker container lifecycle management."""

import time
import uuid
import docker
from dataclasses import dataclass
from pathlib import Path
from shlex import quote as shell_quote
from docker.errors import DockerException, NotFound, ImageNotFound
from ghost.config import (
    DOCKER_BASE_IMAGE,
    DOCKER_CONTAINER_PREFIX,
    DEFAULT_COMMAND_TIMEOUT,
)


@dataclass
class ExecResult:
    """Result of executing a command in the container."""

    stdout: str
    stderr: str
    exit_code: int
    duration: float
    timed_out: bool = False


class GhostContainer:
    """Manages a Docker container for ghost.dev runs."""

    def __init__(self, repo_path: str, timeout: int = DEFAULT_COMMAND_TIMEOUT, verbose: bool = False):
        self.repo_path = Path(repo_path).resolve()
        self.timeout = timeout
        self.verbose = verbose
        self.container = None
        self.client = None
        self.container_name = ""
        self._image_tag = "ghost-dev:latest"

    def start(self) -> str:
        """Create and start the ghost container. Returns container name."""
        try:
            self.client = docker.from_env()
        except DockerException as e:
            raise RuntimeError(
                f"Docker is not available: {e}\n"
                "Install Docker or use --no-docker for doc analysis only."
            )

        self._build_image()

        short_id = uuid.uuid4().hex[:6]
        repo_name = self.repo_path.name.lower().replace(" ", "-")
        self.container_name = f"{DOCKER_CONTAINER_PREFIX}-{repo_name}-{short_id}"

        self.container = self.client.containers.run(
            self._image_tag,
            command="sleep infinity",
            name=self.container_name,
            detach=True,
            volumes={
                str(self.repo_path): {
                    "bind": "/home/ghostdev/repo",
                    "mode": "rw",
                }
            },
            working_dir="/home/ghostdev/repo",
            network_mode="bridge",
            mem_limit="2g",
            cpu_period=100000,
            cpu_quota=200000,  # 2 CPUs
            tmpfs={"/tmp": "size=512M"},  # Fast tmpfs for temp files
        )
        return self.container_name

    def _build_image(self) -> None:
        """Build the ghost Docker image if it doesn't exist."""
        try:
            self.client.images.get(self._image_tag)
        except ImageNotFound:
            dockerfile_dir = Path(__file__).parent
            self.client.images.build(
                path=str(dockerfile_dir),
                dockerfile="Dockerfile.ghost",
                tag=self._image_tag,
                rm=True,
            )

    def exec_command(self, command: str, timeout: int | None = None,
                     env: dict[str, str] | None = None) -> ExecResult:
        """Execute a command inside the container with enforced timeout."""
        if not self.container:
            raise RuntimeError("Container not started")

        timeout = timeout or self.timeout
        # Prepend env vars inline so they're available to the command
        if env:
            exports = " ".join(f'{k}="{v}"' for k, v in env.items())
            command = f"{exports} {command}"
        wrapped = f"bash -c {shell_quote(command)}"
        timed_cmd = f"timeout --signal=KILL {timeout} {wrapped}"

        start_time = time.time()
        timed_out = False

        try:
            exit_code, output = self.container.exec_run(
                timed_cmd,
                demux=True,
                user="ghostdev",
                workdir="/home/ghostdev/repo",
            )
            duration = time.time() - start_time

            stdout = (output[0] or b"").decode("utf-8", errors="replace")
            stderr = (output[1] or b"").decode("utf-8", errors="replace")

            # exit code 137 = killed by timeout (SIGKILL)
            if exit_code == 137 or exit_code == 124:
                timed_out = True

        except Exception as e:
            duration = time.time() - start_time
            stdout = ""
            stderr = str(e)
            exit_code = 1
            timed_out = duration > timeout

        return ExecResult(
            stdout=stdout[:10000],  # Cap output size
            stderr=stderr[:10000],
            exit_code=exit_code,
            duration=round(duration, 2),
            timed_out=timed_out,
        )

    def destroy(self) -> None:
        """Stop and remove the container."""
        if self.container:
            try:
                self.container.stop(timeout=5)
                self.container.remove(force=True)
            except (NotFound, DockerException):
                pass
            self.container = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.destroy()
