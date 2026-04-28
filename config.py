from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


APP_NAME = "NexaPCB"
DEFAULT_WORKSPACE_DIRNAME = "workspace"

FORBIDDEN_ABSOLUTE_PATH_MARKERS = [
    "/Users/",
    "/home/",
    "/tmp/",
    "/Applications/",
]

SUPPORTED_3D_MODEL_SUFFIXES = {".step", ".stp", ".wrl"}
SUPPORTED_SYMBOL_SUFFIXES = {".kicad_sym"}
SUPPORTED_FOOTPRINT_SUFFIXES = {".kicad_mod"}
SUPPORTED_PRETTY_SUFFIX = ".pretty"

JLC_FOOTPRINT_LIB_NAME = "imported_jlc_footprints"
CUSTOM_FOOTPRINT_LIB_NAME = "custom"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    project_name: str

    @property
    def kicad_pro(self) -> Path:
        return self.root / f"{self.project_name}.kicad_pro"

    @property
    def kicad_sch(self) -> Path:
        return self.root / f"{self.project_name}.kicad_sch"

    @property
    def kicad_pcb(self) -> Path:
        return self.root / f"{self.project_name}.kicad_pcb"

    @property
    def netlist_dir(self) -> Path:
        return self.root / "netlist"

    @property
    def xml_file(self) -> Path:
        return self.netlist_dir / f"{self.project_name}.xml"

    @property
    def net_file(self) -> Path:
        return self.netlist_dir / f"{self.project_name}.net"

    @property
    def symbols_dir(self) -> Path:
        return self.root / "symbols"

    @property
    def custom_symbols_dir(self) -> Path:
        return self.symbols_dir / "custom"

    @property
    def footprints_dir(self) -> Path:
        return self.root / "footprints"

    @property
    def imported_footprints_dir(self) -> Path:
        return self.footprints_dir / f"{JLC_FOOTPRINT_LIB_NAME}.pretty"

    @property
    def custom_footprints_dir(self) -> Path:
        return self.footprints_dir / f"{CUSTOM_FOOTPRINT_LIB_NAME}.pretty"

    @property
    def models_dir(self) -> Path:
        return self.root / "3d_models"

    @property
    def custom_models_dir(self) -> Path:
        return self.models_dir / "custom"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def work_dir(self) -> Path:
        return self.root / "work"

    @property
    def import_raw_dir(self) -> Path:
        return self.root / "import_raw"

    def ensure_all(self) -> None:
        for path in [
            self.root,
            self.netlist_dir,
            self.symbols_dir,
            self.custom_symbols_dir,
            self.footprints_dir,
            self.imported_footprints_dir,
            self.custom_footprints_dir,
            self.models_dir,
            self.custom_models_dir,
            self.reports_dir,
            self.logs_dir,
            self.work_dir,
            self.import_raw_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def default_project_root(base_dir: Path, project_name: str) -> Path:
    return base_dir / DEFAULT_WORKSPACE_DIRNAME / project_name


def make_project_paths(project_root: str | Path, project_name: str) -> ProjectPaths:
    root = Path(project_root).expanduser().resolve()
    return ProjectPaths(root=root, project_name=project_name)
