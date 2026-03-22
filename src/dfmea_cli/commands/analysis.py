from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Annotated, Any, Callable, NoReturn

import typer

from dfmea_cli.contracts import failure_result, success_result
from dfmea_cli.db import DEFAULT_BUSY_TIMEOUT_MS, DEFAULT_RETRY
from dfmea_cli.errors import CliError
from dfmea_cli.output import OutputFormat, emit_payload
from dfmea_cli.resolve import ResolvedProjectContext, resolve_project_context
from dfmea_cli.services.analysis import (
    AnalysisDeleteResult,
    AnalysisLinkResult,
    AnalysisMutationResult,
    FailureChainCreateResult,
    TraceLinkResult,
    add_characteristic,
    add_failure_chain,
    add_function,
    add_requirement,
    delete_analysis_node,
    delete_characteristic,
    delete_requirement,
    link_fm_characteristic,
    link_fm_requirement,
    link_trace,
    unlink_fm_characteristic,
    unlink_fm_requirement,
    unlink_trace,
    update_action,
    update_action_status,
    update_failure_cause,
    update_failure_effect,
    update_failure_mode,
    update_characteristic,
    update_function,
    update_requirement,
)


analysis_app = typer.Typer(help="Analysis commands.")

_REPEATED_GROUPING_HELP = (
    "Repeated FE/FC/ACT flags pair by occurrence order. For example, the first "
    "--fc-description pairs with the first --occurrence, first --detection, and first --ap. "
    "Repeated --target-causes values are interpreted as 1-based FC creation-order indexes "
    "within the current request. Use --input for complex chains; it is the preferred path for complex chains."
)


@analysis_app.command("add-function")
def add_function_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    comp: str = typer.Option(..., "--comp"),
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option(..., "--description"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis add-function",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: add_function(
            db_path=context.db_path,
            project_id=context.project_id,
            comp_ref=comp,
            name=name,
            description=description,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_function_data,
    )


@analysis_app.command("update-function")
def update_function_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fn: str = typer.Option(..., "--fn"),
    name: str | None = typer.Option(None, "--name"),
    description: str | None = typer.Option(None, "--description"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-function",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_function(
            db_path=context.db_path,
            project_id=context.project_id,
            fn_ref=fn,
            name=name,
            description=description,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_function_data,
    )


@analysis_app.command("add-requirement")
def add_requirement_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fn: str = typer.Option(..., "--fn"),
    text: str = typer.Option(..., "--text"),
    source: str | None = typer.Option(None, "--source"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis add-requirement",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: add_requirement(
            db_path=context.db_path,
            project_id=context.project_id,
            fn_ref=fn,
            text=text,
            source=source,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_requirement_data,
    )


@analysis_app.command("update-requirement")
def update_requirement_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    req: str = typer.Option(..., "--req"),
    text: str | None = typer.Option(None, "--text"),
    source: str | None = typer.Option(None, "--source"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-requirement",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_requirement(
            db_path=context.db_path,
            project_id=context.project_id,
            req_ref=req,
            text=text,
            source=source,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_requirement_data,
    )


@analysis_app.command("delete-requirement")
def delete_requirement_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    req: str = typer.Option(..., "--req"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis delete-requirement",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: delete_requirement(
            db_path=context.db_path,
            project_id=context.project_id,
            req_ref=req,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_requirement_data,
    )


@analysis_app.command("add-characteristic")
def add_characteristic_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fn: str = typer.Option(..., "--fn"),
    text: str = typer.Option(..., "--text"),
    value: str | None = typer.Option(None, "--value"),
    unit: str | None = typer.Option(None, "--unit"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis add-characteristic",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: add_characteristic(
            db_path=context.db_path,
            project_id=context.project_id,
            fn_ref=fn,
            text=text,
            value=value,
            unit=unit,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_characteristic_data,
    )


@analysis_app.command("update-characteristic")
def update_characteristic_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    char: str = typer.Option(..., "--char"),
    text: str | None = typer.Option(None, "--text"),
    value: str | None = typer.Option(None, "--value"),
    unit: str | None = typer.Option(None, "--unit"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-characteristic",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_characteristic(
            db_path=context.db_path,
            project_id=context.project_id,
            char_ref=char,
            text=text,
            value=value,
            unit=unit,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_characteristic_data,
    )


@analysis_app.command("delete-characteristic")
def delete_characteristic_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    char: str = typer.Option(..., "--char"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis delete-characteristic",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: delete_characteristic(
            db_path=context.db_path,
            project_id=context.project_id,
            char_ref=char,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_characteristic_data,
    )


@analysis_app.command(
    "add-failure-chain",
    help=(
        "Create an FM under an FN and optionally create FE, FC, and ACT children. "
        + _REPEATED_GROUPING_HELP
    ),
)
def add_failure_chain_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fn: str = typer.Option(..., "--fn"),
    input_path: Path | None = typer.Option(
        None,
        "--input",
        exists=False,
        dir_okay=False,
        readable=True,
        help=(
            "Read structured failure-chain JSON from a file. Preferred for complex chains. "
            "In JSON mode, act.target_causes uses 1-based FC creation-order indexes from the same payload."
        ),
    ),
    fm_description: str | None = typer.Option(None, "--fm-description"),
    severity: int | None = typer.Option(None, "--severity"),
    violates_req: Annotated[
        list[int] | None,
        typer.Option(
            "--violates-req", help="REQ rowid. Repeat to add multiple references."
        ),
    ] = None,
    related_char: Annotated[
        list[int] | None,
        typer.Option(
            "--related-char", help="CHAR rowid. Repeat to add multiple references."
        ),
    ] = None,
    fe_description: Annotated[
        list[str] | None,
        typer.Option("--fe-description", help=_REPEATED_GROUPING_HELP),
    ] = None,
    fe_level: Annotated[
        list[str] | None,
        typer.Option("--fe-level", help=_REPEATED_GROUPING_HELP),
    ] = None,
    fc_description: Annotated[
        list[str] | None,
        typer.Option("--fc-description", help=_REPEATED_GROUPING_HELP),
    ] = None,
    occurrence: Annotated[
        list[int] | None,
        typer.Option("--occurrence", help=_REPEATED_GROUPING_HELP),
    ] = None,
    detection: Annotated[
        list[int] | None,
        typer.Option("--detection", help=_REPEATED_GROUPING_HELP),
    ] = None,
    ap: Annotated[
        list[str] | None,
        typer.Option("--ap", help=_REPEATED_GROUPING_HELP),
    ] = None,
    act_description: Annotated[
        list[str] | None,
        typer.Option("--act-description", help=_REPEATED_GROUPING_HELP),
    ] = None,
    kind: Annotated[
        list[str] | None,
        typer.Option("--kind", help=_REPEATED_GROUPING_HELP),
    ] = None,
    status: Annotated[
        list[str] | None,
        typer.Option("--status", help=_REPEATED_GROUPING_HELP),
    ] = None,
    owner: Annotated[
        list[str] | None,
        typer.Option("--owner", help=_REPEATED_GROUPING_HELP),
    ] = None,
    due: Annotated[
        list[str] | None,
        typer.Option("--due", help=_REPEATED_GROUPING_HELP),
    ] = None,
    target_causes: Annotated[
        list[str] | None,
        typer.Option(
            "--target-causes",
            help=(
                "Comma-separated FC creation-order indexes for the ACT item. In repeated-flag mode these are "
                "1-based FC creation-order indexes within the current request, not stored FC rowids. "
                + _REPEATED_GROUPING_HELP
            ),
        ),
    ] = None,
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_failure_chain_command(
        command_name="analysis add-failure-chain",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: add_failure_chain(
            db_path=context.db_path,
            project_id=context.project_id,
            fn_ref=fn,
            chain_spec=_load_failure_chain_input(
                input_path=input_path,
                fm_description=fm_description,
                severity=severity,
                violates_req=violates_req,
                related_char=related_char,
                fe_descriptions=fe_description,
                fe_levels=fe_level,
                fc_descriptions=fc_description,
                occurrences=occurrence,
                detections=detection,
                aps=ap,
                act_descriptions=act_description,
                kinds=kind,
                statuses=status,
                owners=owner,
                dues=due,
                target_causes=target_causes,
            ),
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@analysis_app.command("update-fm")
def update_fm_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fm: str = typer.Option(..., "--fm"),
    description: str | None = typer.Option(None, "--description"),
    severity: int | None = typer.Option(None, "--severity"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-fm",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_failure_mode(
            db_path=context.db_path,
            project_id=context.project_id,
            fm_ref=fm,
            description=description,
            severity=severity,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_fm_data,
    )


@analysis_app.command("update-fe")
def update_fe_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fe: str = typer.Option(..., "--fe"),
    description: str | None = typer.Option(None, "--description"),
    level: str | None = typer.Option(None, "--level"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-fe",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_failure_effect(
            db_path=context.db_path,
            project_id=context.project_id,
            fe_ref=fe,
            description=description,
            level=level,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_fe_data,
    )


@analysis_app.command("update-fc")
def update_fc_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fc: str = typer.Option(..., "--fc"),
    description: str | None = typer.Option(None, "--description"),
    occurrence: int | None = typer.Option(None, "--occurrence"),
    detection: int | None = typer.Option(None, "--detection"),
    ap: str | None = typer.Option(None, "--ap"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-fc",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_failure_cause(
            db_path=context.db_path,
            project_id=context.project_id,
            fc_ref=fc,
            description=description,
            occurrence=occurrence,
            detection=detection,
            ap=ap,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_fc_data,
    )


@analysis_app.command("update-act")
def update_act_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    act: str = typer.Option(..., "--act"),
    description: str | None = typer.Option(None, "--description"),
    kind: str | None = typer.Option(None, "--kind"),
    status: str | None = typer.Option(None, "--status"),
    owner: str | None = typer.Option(None, "--owner"),
    due: str | None = typer.Option(None, "--due"),
    target_causes: str | None = typer.Option(None, "--target-causes"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-act",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_action(
            db_path=context.db_path,
            project_id=context.project_id,
            act_ref=act,
            description=description,
            kind=kind,
            status=status,
            owner=owner,
            due=due,
            target_causes=_parse_fc_rowid_list(target_causes)
            if target_causes is not None
            else None,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_act_data,
    )


@analysis_app.command("update-action-status")
def update_action_status_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    act: str = typer.Option(..., "--act"),
    status: str = typer.Option(..., "--status"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_analysis_command(
        command_name="analysis update-action-status",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: update_action_status(
            db_path=context.db_path,
            project_id=context.project_id,
            act_ref=act,
            status=status,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_act_data,
    )


@analysis_app.command("link-fm-requirement")
def link_fm_requirement_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fm: str = typer.Option(..., "--fm"),
    req: str = typer.Option(..., "--req"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_link_command(
        command_name="analysis link-fm-requirement",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: link_fm_requirement(
            db_path=context.db_path,
            project_id=context.project_id,
            fm_ref=fm,
            req_ref=req,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_linked_req_data,
    )


@analysis_app.command("unlink-fm-requirement")
def unlink_fm_requirement_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fm: str = typer.Option(..., "--fm"),
    req: str = typer.Option(..., "--req"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_link_command(
        command_name="analysis unlink-fm-requirement",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: unlink_fm_requirement(
            db_path=context.db_path,
            project_id=context.project_id,
            fm_ref=fm,
            req_ref=req,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_linked_req_data,
    )


@analysis_app.command("link-fm-characteristic")
def link_fm_characteristic_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fm: str = typer.Option(..., "--fm"),
    char: str = typer.Option(..., "--char"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_link_command(
        command_name="analysis link-fm-characteristic",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: link_fm_characteristic(
            db_path=context.db_path,
            project_id=context.project_id,
            fm_ref=fm,
            char_ref=char,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_linked_char_data,
    )


@analysis_app.command("unlink-fm-characteristic")
def unlink_fm_characteristic_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    fm: str = typer.Option(..., "--fm"),
    char: str = typer.Option(..., "--char"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_link_command(
        command_name="analysis unlink-fm-characteristic",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: unlink_fm_characteristic(
            db_path=context.db_path,
            project_id=context.project_id,
            fm_ref=fm,
            char_ref=char,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
        build_data=_build_linked_char_data,
    )


@analysis_app.command("link-trace")
def link_trace_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    from_ref: str = typer.Option(..., "--from"),
    to_fm: str = typer.Option(..., "--to-fm"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_trace_link_command(
        command_name="analysis link-trace",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: link_trace(
            db_path=context.db_path,
            project_id=context.project_id,
            from_ref=from_ref,
            to_fm_ref=to_fm,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@analysis_app.command("unlink-trace")
def unlink_trace_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    from_ref: str = typer.Option(..., "--from"),
    to_fm: str = typer.Option(..., "--to-fm"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_trace_link_command(
        command_name="analysis unlink-trace",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: unlink_trace(
            db_path=context.db_path,
            project_id=context.project_id,
            from_ref=from_ref,
            to_fm_ref=to_fm,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


@analysis_app.command("delete-node")
def delete_node_command(
    db: Path = typer.Option(..., "--db", exists=False, dir_okay=False, readable=True),
    project: str | None = typer.Option(None, "--project"),
    node: str = typer.Option(..., "--node"),
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--format"),
    quiet: bool = typer.Option(False, "--quiet"),
    busy_timeout_ms: int = typer.Option(DEFAULT_BUSY_TIMEOUT_MS, "--busy-timeout-ms"),
    retry: int = typer.Option(DEFAULT_RETRY, "--retry"),
) -> None:
    _run_delete_command(
        command_name="analysis delete-node",
        db=db,
        project=project,
        output_format=output_format,
        quiet=quiet,
        busy_timeout_ms=busy_timeout_ms,
        retry=retry,
        action=lambda context: delete_analysis_node(
            db_path=context.db_path,
            project_id=context.project_id,
            node_ref=node,
            busy_timeout_ms=context.retry_policy.busy_timeout_ms,
            retry=context.retry_policy.retry,
        ),
    )


def _build_function_data(result: AnalysisMutationResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fn_id": result.node_id,
        "parent_comp_id": result.parent_id,
        "affected_objects": [
            {"type": result.node_type, "id": result.node_id, "rowid": result.rowid}
        ],
    }


def _build_requirement_data(result: AnalysisMutationResult) -> dict[str, Any]:
    affected_objects = result.affected_objects or [
        {"type": result.node_type, "rowid": result.rowid}
    ]
    return {
        "project_id": result.project_id,
        "fn_id": result.parent_id,
        "req_rowid": result.rowid,
        "affected_objects": affected_objects,
    }


def _build_characteristic_data(result: AnalysisMutationResult) -> dict[str, Any]:
    affected_objects = result.affected_objects or [
        {"type": result.node_type, "rowid": result.rowid}
    ]
    return {
        "project_id": result.project_id,
        "fn_id": result.parent_id,
        "char_rowid": result.rowid,
        "affected_objects": affected_objects,
    }


def _build_fm_data(result: AnalysisMutationResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fn_id": result.parent_id,
        "fm_id": result.node_id,
        "fm_rowid": result.rowid,
        "affected_objects": [
            {"type": result.node_type, "id": result.node_id, "rowid": result.rowid}
        ],
    }


def _build_fe_data(result: AnalysisMutationResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fm_id": result.parent_id,
        "fe_rowid": result.rowid,
        "affected_objects": [{"type": result.node_type, "rowid": result.rowid}],
    }


def _build_fc_data(result: AnalysisMutationResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fm_id": result.parent_id,
        "fc_rowid": result.rowid,
        "affected_objects": [{"type": result.node_type, "rowid": result.rowid}],
    }


def _build_act_data(result: AnalysisMutationResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fm_id": result.parent_id,
        "act_id": result.node_id,
        "act_rowid": result.rowid,
        "affected_objects": [
            {"type": result.node_type, "id": result.node_id, "rowid": result.rowid}
        ],
    }


def _build_linked_req_data(result: AnalysisLinkResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fn_id": result.fn_id,
        "fm_id": result.fm_id,
        "req_rowid": result.linked_rowid,
        "affected_objects": [
            {"type": "FM", "id": result.fm_id, "rowid": result.fm_rowid},
            {"type": "REQ", "rowid": result.linked_rowid},
        ],
    }


def _build_linked_char_data(result: AnalysisLinkResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fn_id": result.fn_id,
        "fm_id": result.fm_id,
        "char_rowid": result.linked_rowid,
        "affected_objects": [
            {"type": "FM", "id": result.fm_id, "rowid": result.fm_rowid},
            {"type": "CHAR", "rowid": result.linked_rowid},
        ],
    }


def _build_trace_link_data(result: TraceLinkResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "from": {"type": result.from_type, "rowid": result.from_rowid},
        "to_fm": {"id": result.to_fm_id, "rowid": result.to_fm_rowid},
        "affected_objects": [
            {"type": result.from_type, "rowid": result.from_rowid},
            {"type": "FM", "id": result.to_fm_id, "rowid": result.to_fm_rowid},
        ],
    }


def _build_delete_data(result: AnalysisDeleteResult) -> dict[str, Any]:
    deleted_node = {"type": result.deleted_type, "rowid": result.deleted_rowid}
    if result.deleted_id is not None:
        deleted_node["id"] = result.deleted_id
    return {
        "project_id": result.project_id,
        "deleted_node": deleted_node,
        "affected_objects": result.affected_objects,
    }


def _build_failure_chain_data(result: FailureChainCreateResult) -> dict[str, Any]:
    return {
        "project_id": result.project_id,
        "fn_id": result.fn_id,
        "fm_id": result.fm_id,
        "fm_rowid": result.fm_rowid,
        "affected_objects": result.affected_objects,
    }


def _emit_failure(
    *,
    command_name: str,
    output_format: OutputFormat,
    error: CliError,
    meta: dict[str, Any],
) -> NoReturn:
    payload = failure_result(command=command_name, errors=[error.to_error()], meta=meta)
    emit_payload(
        payload,
        output_format=output_format,
        quiet=False,
        exit_code=error.resolved_exit_code,
    )
    raise AssertionError("unreachable")


def _run_analysis_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], AnalysisMutationResult],
    build_data: Callable[[AnalysisMutationResult], dict[str, Any]],
) -> NoReturn:
    meta = {
        "db": str(db),
        "project_id": project,
        "busy_timeout_ms": busy_timeout_ms,
        "retry": retry,
    }
    try:
        context = resolve_project_context(
            db_path=db,
            project_id=project,
            busy_timeout_ms=busy_timeout_ms,
            retry=retry,
        )
        meta = {
            "db": str(context.db_path),
            "project_id": context.project_id,
            "busy_timeout_ms": context.retry_policy.busy_timeout_ms,
            "retry": context.retry_policy.retry,
        }
        result = action(context)
    except CliError as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=exc,
            meta=meta,
        )
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=_normalize_analysis_command_error(exc=exc, meta=meta),
            meta=meta,
        )

    payload = success_result(command=command_name, data=build_data(result), meta=meta)
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")


def _run_failure_chain_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], FailureChainCreateResult],
) -> NoReturn:
    meta = {
        "db": str(db),
        "project_id": project,
        "busy_timeout_ms": busy_timeout_ms,
        "retry": retry,
    }
    try:
        context = resolve_project_context(
            db_path=db,
            project_id=project,
            busy_timeout_ms=busy_timeout_ms,
            retry=retry,
        )
        meta = {
            "db": str(context.db_path),
            "project_id": context.project_id,
            "busy_timeout_ms": context.retry_policy.busy_timeout_ms,
            "retry": context.retry_policy.retry,
        }
        result = action(context)
    except CliError as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=exc,
            meta=meta,
        )
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=_normalize_analysis_command_error(exc=exc, meta=meta),
            meta=meta,
        )

    payload = success_result(
        command=command_name, data=_build_failure_chain_data(result), meta=meta
    )
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")


def _run_link_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], AnalysisLinkResult],
    build_data: Callable[[AnalysisLinkResult], dict[str, Any]],
) -> NoReturn:
    meta = {
        "db": str(db),
        "project_id": project,
        "busy_timeout_ms": busy_timeout_ms,
        "retry": retry,
    }
    try:
        context = resolve_project_context(
            db_path=db,
            project_id=project,
            busy_timeout_ms=busy_timeout_ms,
            retry=retry,
        )
        meta = {
            "db": str(context.db_path),
            "project_id": context.project_id,
            "busy_timeout_ms": context.retry_policy.busy_timeout_ms,
            "retry": context.retry_policy.retry,
        }
        result = action(context)
    except CliError as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=exc,
            meta=meta,
        )
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=_normalize_analysis_command_error(exc=exc, meta=meta),
            meta=meta,
        )

    payload = success_result(command=command_name, data=build_data(result), meta=meta)
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")


def _run_trace_link_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], TraceLinkResult],
) -> NoReturn:
    meta = {
        "db": str(db),
        "project_id": project,
        "busy_timeout_ms": busy_timeout_ms,
        "retry": retry,
    }
    try:
        context = resolve_project_context(
            db_path=db,
            project_id=project,
            busy_timeout_ms=busy_timeout_ms,
            retry=retry,
        )
        meta = {
            "db": str(context.db_path),
            "project_id": context.project_id,
            "busy_timeout_ms": context.retry_policy.busy_timeout_ms,
            "retry": context.retry_policy.retry,
        }
        result = action(context)
    except CliError as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=exc,
            meta=meta,
        )
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=_normalize_analysis_command_error(exc=exc, meta=meta),
            meta=meta,
        )

    payload = success_result(
        command=command_name, data=_build_trace_link_data(result), meta=meta
    )
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")


def _run_delete_command(
    *,
    command_name: str,
    db: Path,
    project: str | None,
    output_format: OutputFormat,
    quiet: bool,
    busy_timeout_ms: int,
    retry: int,
    action: Callable[[ResolvedProjectContext], AnalysisDeleteResult],
) -> NoReturn:
    meta = {
        "db": str(db),
        "project_id": project,
        "busy_timeout_ms": busy_timeout_ms,
        "retry": retry,
    }
    try:
        context = resolve_project_context(
            db_path=db,
            project_id=project,
            busy_timeout_ms=busy_timeout_ms,
            retry=retry,
        )
        meta = {
            "db": str(context.db_path),
            "project_id": context.project_id,
            "busy_timeout_ms": context.retry_policy.busy_timeout_ms,
            "retry": context.retry_policy.retry,
        }
        result = action(context)
    except CliError as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=exc,
            meta=meta,
        )
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        _emit_failure(
            command_name=command_name,
            output_format=output_format,
            error=_normalize_analysis_command_error(exc=exc, meta=meta),
            meta=meta,
        )

    payload = success_result(
        command=command_name, data=_build_delete_data(result), meta=meta
    )
    emit_payload(payload, output_format=output_format, quiet=quiet)
    raise AssertionError("unreachable")


def _load_failure_chain_input(
    *,
    input_path: Path | None,
    fm_description: str | None,
    severity: int | None,
    violates_req: list[int] | None,
    related_char: list[int] | None,
    fe_descriptions: list[str] | None,
    fe_levels: list[str] | None,
    fc_descriptions: list[str] | None,
    occurrences: list[int] | None,
    detections: list[int] | None,
    aps: list[str] | None,
    act_descriptions: list[str] | None,
    kinds: list[str] | None,
    statuses: list[str] | None,
    owners: list[str] | None,
    dues: list[str] | None,
    target_causes: list[str] | None,
) -> dict[str, Any]:
    if input_path is not None:
        conflicting_flags = _find_conflicting_failure_chain_flags(
            fm_description=fm_description,
            severity=severity,
            violates_req=violates_req,
            related_char=related_char,
            fe_descriptions=fe_descriptions,
            fe_levels=fe_levels,
            fc_descriptions=fc_descriptions,
            occurrences=occurrences,
            detections=detections,
            aps=aps,
            act_descriptions=act_descriptions,
            kinds=kinds,
            statuses=statuses,
            owners=owners,
            dues=dues,
            target_causes=target_causes,
        )
        if conflicting_flags:
            raise CliError(
                code="INVALID_REFERENCE",
                message="--input cannot be combined with failure-chain creation flags.",
                target={"input": str(input_path), "conflicts": conflicting_flags},
                suggested_action="Use either --input or repeated creation flags, but not both in the same command.",
            )
        try:
            return json.loads(input_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CliError(
                code="INVALID_REFERENCE",
                message=f"Failure-chain input file '{input_path}' does not exist.",
                target={"input": str(input_path)},
                suggested_action="Provide an existing JSON file path for --input.",
            ) from exc
        except json.JSONDecodeError as exc:
            raise CliError(
                code="INVALID_REFERENCE",
                message=f"Failure-chain input file '{input_path}' contains malformed JSON.",
                target={"input": str(input_path)},
                suggested_action="Fix the JSON file and retry the command.",
            ) from exc

    if fm_description is None or severity is None:
        raise CliError(
            code="INVALID_REFERENCE",
            message="Repeated-flag mode requires --fm-description and --severity.",
            target={"field": "fm"},
            suggested_action="Provide --fm-description and --severity, or use --input for structured mode.",
        )

    return {
        "fm": {
            "description": fm_description,
            "severity": severity,
            "violates_requirements": list(violates_req or []),
            "related_characteristics": list(related_char or []),
        },
        "fe": _group_fe_flags(
            descriptions=list(fe_descriptions or []), levels=list(fe_levels or [])
        ),
        "fc": _group_fc_flags(
            descriptions=list(fc_descriptions or []),
            occurrences=list(occurrences or []),
            detections=list(detections or []),
            aps=list(aps or []),
        ),
        "act": _group_act_flags(
            descriptions=list(act_descriptions or []),
            kinds=list(kinds or []),
            statuses=list(statuses or []),
            owners=list(owners or []),
            dues=list(dues or []),
            target_causes=list(target_causes or []),
        ),
    }


def _find_conflicting_failure_chain_flags(
    *,
    fm_description: str | None,
    severity: int | None,
    violates_req: list[int] | None,
    related_char: list[int] | None,
    fe_descriptions: list[str] | None,
    fe_levels: list[str] | None,
    fc_descriptions: list[str] | None,
    occurrences: list[int] | None,
    detections: list[int] | None,
    aps: list[str] | None,
    act_descriptions: list[str] | None,
    kinds: list[str] | None,
    statuses: list[str] | None,
    owners: list[str] | None,
    dues: list[str] | None,
    target_causes: list[str] | None,
) -> list[str]:
    candidates = [
        ("--fm-description", fm_description),
        ("--severity", severity),
        ("--violates-req", violates_req),
        ("--related-char", related_char),
        ("--fe-description", fe_descriptions),
        ("--fe-level", fe_levels),
        ("--fc-description", fc_descriptions),
        ("--occurrence", occurrences),
        ("--detection", detections),
        ("--ap", aps),
        ("--act-description", act_descriptions),
        ("--kind", kinds),
        ("--status", statuses),
        ("--owner", owners),
        ("--due", dues),
        ("--target-causes", target_causes),
    ]
    return [name for name, value in candidates if value not in (None, [])]


def _group_fe_flags(
    *, descriptions: list[str], levels: list[str]
) -> list[dict[str, Any]]:
    count = max(len(descriptions), len(levels))
    return [
        {
            "description": _required_group_value(
                descriptions, index=index, field="--fe-description", group="FE"
            ),
            "level": _optional_group_value(levels, index=index),
        }
        for index in range(count)
    ]


def _group_fc_flags(
    *,
    descriptions: list[str],
    occurrences: list[int],
    detections: list[int],
    aps: list[str],
) -> list[dict[str, Any]]:
    count = max(len(descriptions), len(occurrences), len(detections), len(aps))
    return [
        {
            "description": _required_group_value(
                descriptions, index=index, field="--fc-description", group="FC"
            ),
            "occurrence": _required_group_value(
                occurrences, index=index, field="--occurrence", group="FC"
            ),
            "detection": _required_group_value(
                detections, index=index, field="--detection", group="FC"
            ),
            "ap": _required_group_value(aps, index=index, field="--ap", group="FC"),
        }
        for index in range(count)
    ]


def _group_act_flags(
    *,
    descriptions: list[str],
    kinds: list[str],
    statuses: list[str],
    owners: list[str],
    dues: list[str],
    target_causes: list[str],
) -> list[dict[str, Any]]:
    count = max(
        len(descriptions),
        len(kinds),
        len(statuses),
        len(owners),
        len(dues),
        len(target_causes),
    )
    return [
        {
            "description": _required_group_value(
                descriptions, index=index, field="--act-description", group="ACT"
            ),
            "kind": _optional_group_value(kinds, index=index),
            "status": _optional_group_value(statuses, index=index),
            "owner": _optional_group_value(owners, index=index),
            "due": _optional_group_value(dues, index=index),
            "target_causes": _parse_rowid_list(
                _optional_group_value(target_causes, index=index)
            ),
        }
        for index in range(count)
    ]


def _required_group_value(
    values: list[Any], *, index: int, field: str, group: str
) -> Any:
    if index < len(values):
        return values[index]
    raise CliError(
        code="INVALID_REFERENCE",
        message=f"{group} repeated flags pair by occurrence order and require {field} for item {index + 1}.",
        target={"field": field, "group": group, "index": index + 1},
        suggested_action=(
            f"Add {field} for {group} item {index + 1}, or use --input for complex chains."
        ),
    )


def _optional_group_value(values: list[Any], *, index: int) -> Any | None:
    if index < len(values):
        return values[index]
    return None


def _parse_rowid_list(raw_value: str | None) -> list[int]:
    if raw_value is None or raw_value.strip() == "":
        return []
    try:
        return [int(part.strip()) for part in raw_value.split(",") if part.strip()]
    except ValueError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message="--target-causes must be a comma-separated list of 1-based FC creation-order indexes.",
            target={"field": "--target-causes", "value": raw_value},
            suggested_action="Use comma-separated integer indexes like 1 or 1,2.",
        ) from exc


def _parse_fc_rowid_list(raw_value: str | None) -> list[int]:
    if raw_value is None or raw_value.strip() == "":
        return []
    values: list[int] = []
    try:
        for part in raw_value.split(","):
            stripped = part.strip()
            if not stripped:
                continue
            rowid = int(stripped)
            if rowid < 1:
                raise ValueError("rowid must be positive")
            values.append(rowid)
        return values
    except ValueError as exc:
        raise CliError(
            code="INVALID_REFERENCE",
            message="--target-causes must be a comma-separated list of FM-local FC rowids.",
            target={"field": "--target-causes", "value": raw_value},
            suggested_action="Use comma-separated FC rowids like 6 or 6,7.",
        ) from exc


def _normalize_analysis_command_error(
    *, exc: sqlite3.Error | json.JSONDecodeError, meta: dict[str, Any]
) -> CliError:
    if isinstance(exc, sqlite3.Error):
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            return CliError(
                code="DB_BUSY",
                message="Database is busy and retries were exhausted.",
                target={"db": meta["db"]},
                suggested_action="Retry later or increase --busy-timeout-ms and --retry.",
            )
        return CliError(
            code="UNKNOWN",
            message="Analysis command failed due to a SQLite error.",
            target={"db": meta["db"], "project_id": meta.get("project_id")},
            suggested_action="Retry the command. If it persists, inspect SQLite state and database integrity.",
        )
    return CliError(
        code="INVALID_REFERENCE",
        message="Analysis command encountered malformed JSON data.",
        target={"db": meta["db"], "project_id": meta.get("project_id")},
        suggested_action="Repair malformed JSON inputs or stored node/project data before retrying.",
    )
