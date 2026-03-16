"""Docpick CLI interface."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(package_name="docpick")
def main():
    """Docpick — Document in, Structured JSON out."""
    pass


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--schema", "-s", default=None, help="Schema name (e.g., invoice, receipt) or path to JSON schema file")
@click.option("--output", "-o", default=None, help="Output file path (default: stdout)")
@click.option("--mode", "-m", default="auto", type=click.Choice(["auto", "ocr+llm", "vlm", "ocr_only"]))
@click.option("--ocr", default=None, help="OCR engine (auto, paddle, easyocr)")
@click.option("--llm", default=None, help="LLM provider (vllm, ollama)")
@click.option("--lang", default=None, help="Languages (comma-separated, e.g., ko,en)")
def extract(file: str, schema: str | None, output: str | None, mode: str, ocr: str | None, llm: str | None, lang: str | None):
    """Extract structured data from a document."""
    from docpick.core.config import DocpickConfig
    from docpick.core.pipeline import DocpickPipeline

    config = DocpickConfig.load()
    if ocr:
        config.ocr.engine = ocr
    if llm:
        config.llm.provider = llm

    pipeline = DocpickPipeline(config)
    languages = lang.split(",") if lang else None

    # Resolve schema
    schema_class = None
    if schema:
        schema_class = _resolve_schema(schema)

    with console.status("[bold green]Extracting..."):
        result = pipeline.extract(file, schema=schema_class, mode=mode, languages=languages)

    # Output
    json_str = result.to_json(pretty=True)
    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        console.print(f"[green]Saved to {output}")
    else:
        console.print_json(json_str)

    # Summary
    if result.validation.errors:
        console.print(f"\n[red]Validation errors: {len(result.validation.errors)}")
        for e in result.validation.errors:
            console.print(f"  [red]- {e.field}: {e.message}")
    if result.validation.warnings:
        console.print(f"\n[yellow]Warnings: {len(result.validation.warnings)}")
        for w in result.validation.warnings:
            console.print(f"  [yellow]- {w.field}: {w.message}")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", default="text", type=click.Choice(["text", "markdown"]))
@click.option("--lang", default=None, help="Languages (comma-separated)")
def ocr(file: str, fmt: str, lang: str | None):
    """Run OCR only (no LLM extraction)."""
    from docpick.core.config import DocpickConfig
    from docpick.core.pipeline import DocpickPipeline

    pipeline = DocpickPipeline(DocpickConfig.load())
    languages = lang.split(",") if lang else None

    with console.status("[bold green]Running OCR..."):
        result = pipeline.extract(file, mode="ocr_only", languages=languages)

    if fmt == "markdown":
        console.print(result.markdown)
    else:
        console.print(result.text)

    console.print(f"\n[dim]Engine: {result.ocr_result.engine if result.ocr_result else 'unknown'}, "
                   f"Time: {result.processing_time_ms:.0f}ms")


@main.group()
def schemas():
    """Manage document schemas."""
    pass


@schemas.command(name="list")
def schemas_list():
    """List available schemas."""
    from docpick.schemas import schema_registry

    table = Table(title="Available Schemas")
    table.add_column("Name", style="cyan")
    table.add_column("Fields", style="green")
    table.add_column("Description")

    for name in schema_registry.names():
        cls = schema_registry.get(name)
        fields = len(cls.model_fields)
        doc = cls.__doc__ or ""
        first_line = doc.strip().split("\n")[0] if doc.strip() else ""
        table.add_row(name, str(fields), first_line)

    console.print(table)


@schemas.command(name="show")
@click.argument("name")
def schemas_show(name: str):
    """Show schema details."""
    from docpick.schemas import schema_registry

    cls = schema_registry.get(name)
    schema_json = json.dumps(cls.model_json_schema(), indent=2, ensure_ascii=False)
    console.print_json(schema_json)


@main.group()
def config():
    """Manage Docpick configuration."""
    pass


@config.command(name="show")
def config_show():
    """Show current configuration."""
    from docpick.core.config import DocpickConfig
    cfg = DocpickConfig.load()
    console.print_json(json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False))


@config.command(name="set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value (e.g., docpick config set llm.provider ollama)."""
    from docpick.core.config import DocpickConfig
    cfg = DocpickConfig.load()
    data = cfg.model_dump()

    # Navigate nested keys
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            console.print(f"[red]Unknown key: {key}")
            sys.exit(1)
        current = current[part]
    current[parts[-1]] = value

    new_cfg = DocpickConfig(**data)
    new_cfg.save()
    console.print(f"[green]Set {key} = {value}")


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--schema", "-s", required=True, help="Schema name or path to JSON schema file")
@click.option("--output", "-o", default=None, help="Output file path (default: stdout)")
def validate(file: str, schema: str, output: str | None):
    """Validate extracted JSON data against a schema's rules."""
    schema_class = _resolve_schema(schema)

    # Load JSON data
    data = json.loads(Path(file).read_text(encoding="utf-8"))
    if "data" in data and isinstance(data["data"], dict):
        data = data["data"]  # Support ExtractionResult JSON format

    # Get validation rules
    rules_class = getattr(schema_class, "ValidationRules", None)
    if rules_class is None:
        console.print(f"[yellow]Schema '{schema}' has no validation rules defined")
        return

    rules = getattr(rules_class, "rules", [])
    if not rules:
        console.print(f"[yellow]Schema '{schema}' has no validation rules")
        return

    from docpick.validation.base import Validator
    validator = Validator(rules)
    result = validator.validate(data)

    # Output
    output_data = {
        "is_valid": result.is_valid,
        "rules_applied": result.rules_applied,
        "rules_passed": result.rules_passed,
        "errors": [
            {"field": e.field, "rule": e.rule, "message": e.message}
            for e in result.errors
        ],
        "warnings": [
            {"field": w.field, "rule": w.rule, "message": w.message}
            for w in result.warnings
        ],
    }

    json_str = json.dumps(output_data, indent=2, ensure_ascii=False)
    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        console.print(f"[green]Saved to {output}")
    else:
        console.print_json(json_str)

    # Summary
    if result.is_valid:
        console.print(f"\n[green]✓ Valid ({result.rules_passed}/{result.rules_applied} rules passed)")
    else:
        console.print(f"\n[red]✗ Invalid ({len(result.errors)} errors)")
        for e in result.errors:
            console.print(f"  [red]- {e.field}: {e.message}")
    if result.warnings:
        console.print(f"[yellow]  {len(result.warnings)} warning(s)")
        for w in result.warnings:
            console.print(f"  [yellow]- {w.field}: {w.message}")


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--schema", "-s", default=None, help="Schema name or path to JSON schema file")
@click.option("--output", "-o", default=None, help="Output directory for results")
@click.option("--mode", "-m", default="auto", type=click.Choice(["auto", "ocr+llm", "vlm", "ocr_only"]))
@click.option("--concurrency", "-c", default=4, help="Number of parallel workers")
@click.option("--recursive", "-r", is_flag=True, help="Search subdirectories")
@click.option("--lang", default=None, help="Languages (comma-separated)")
def batch(directory: str, schema: str | None, output: str | None, mode: str, concurrency: int, recursive: bool, lang: str | None):
    """Process all documents in a directory."""
    from docpick.batch import BatchProcessor

    config_obj = _load_config()
    processor = BatchProcessor(config=config_obj, concurrency=concurrency)

    schema_class = _resolve_schema(schema) if schema else None
    languages = lang.split(",") if lang else None

    # Output directory
    output_dir = Path(output) if output else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Progress bar
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=0)

        def on_progress(completed: int, total: int) -> None:
            progress.update(task, total=total, completed=completed)

        # Find files first to set total
        from docpick.batch import SUPPORTED_EXTENSIONS
        dir_path = Path(directory)
        if recursive:
            files = [f for f in dir_path.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS]
        else:
            files = [f for f in dir_path.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]

        if not files:
            console.print("[yellow]No supported documents found")
            return

        progress.update(task, total=len(files))

        result = processor.process_directory(
            directory,
            schema=schema_class,
            mode=mode,
            languages=languages,
            recursive=recursive,
            on_progress=on_progress,
        )

    # Save results
    if output_dir:
        for file_path, extraction in result.results.items():
            out_name = Path(file_path).stem + ".json"
            out_path = output_dir / out_name
            out_path.write_text(extraction.to_json(pretty=True), encoding="utf-8")
        console.print(f"[green]Results saved to {output_dir}/")

    # Summary
    console.print()
    summary = Table(title="Batch Summary")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_row("Total", str(result.total))
    summary.add_row("Succeeded", str(result.succeeded))
    summary.add_row("Failed", str(result.failed))
    summary.add_row("Time", f"{result.processing_time_ms:.0f}ms")
    console.print(summary)

    if result.errors:
        console.print("\n[red]Errors:")
        for file_path, error in result.errors.items():
            console.print(f"  [red]- {Path(file_path).name}: {error}")


def _load_config():
    """Load config, used by multiple commands."""
    from docpick.core.config import DocpickConfig
    return DocpickConfig.load()


def _resolve_schema(name: str):
    """Resolve schema by name or file path."""
    # Try built-in registry first
    from docpick.schemas import schema_registry
    try:
        return schema_registry.get(name)
    except KeyError:
        pass

    # Try as JSON schema file
    path = Path(name)
    if path.exists() and path.suffix == ".json":
        return _load_json_schema_file(path)

    console.print(f"[red]Unknown schema: {name}")
    console.print(f"Available: {', '.join(schema_registry.names())}")
    sys.exit(1)


def _load_json_schema_file(path: Path):
    """Create a dynamic Pydantic model from a JSON Schema file."""
    from pydantic import create_model
    from docpick.schemas.base import DocumentSchema

    schema_data = json.loads(path.read_text(encoding="utf-8"))
    properties = schema_data.get("properties", {})
    required = set(schema_data.get("required", []))

    field_definitions: dict = {}
    for field_name, field_info in properties.items():
        field_type = _json_type_to_python(field_info.get("type", "string"))
        if field_name in required:
            field_definitions[field_name] = (field_type, ...)
        else:
            field_definitions[field_name] = (field_type | None, None)

    model_name = schema_data.get("title", path.stem.replace("-", "_").replace(" ", "_"))
    return create_model(model_name, __base__=DocumentSchema, **field_definitions)


def _json_type_to_python(json_type: str) -> type:
    """Map JSON Schema type to Python type."""
    mapping: dict[str, type] = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
    }
    return mapping.get(json_type, str)


if __name__ == "__main__":
    main()
