"""
Command-line interface for the Autonomous AI Worker.

Usage:
  python cli.py run "Find the latest invoice from Acme Supplies"
  python cli.py run "List all unpaid invoices" --max-iter 10
  python cli.py demo
"""
from __future__ import annotations

import asyncio
import json
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agent.executor import run_task
from agent.models import TaskStatus

app = typer.Typer(help="Autonomous AI Worker CLI")
console = Console()


@app.command()
def run(
    task: str = typer.Argument(..., help="Natural language task description"),
    max_iter: int = typer.Option(15, "--max-iter", "-n", help="Maximum agent iterations"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full scratchpad"),
):
    """Run a task autonomously."""
    console.print(Panel(f"[bold cyan]🤖 Autonomous AI Worker[/bold cyan]\n[white]{task}[/white]", expand=False))

    async def _run():
        state = await run_task(task, max_iterations=max_iter)
        return state

    state = asyncio.run(_run())

    # ── Status ────────────────────────────────────────────────────────────
    status_color = {
        TaskStatus.COMPLETED: "green",
        TaskStatus.FAILED: "red",
        TaskStatus.WAITING_APPROVAL: "yellow",
    }.get(state.status, "white")

    console.print(f"\n[bold]Status:[/bold] [{status_color}]{state.status.upper()}[/{status_color}]")

    # ── Steps ─────────────────────────────────────────────────────────────
    table = Table(title="Agent Steps", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Action", style="cyan")
    table.add_column("Status", width=10)
    table.add_column("Description / Output", style="white")

    icons = {"success": "✅", "failed": "❌", "pending": "⏳", "retried": "🔄"}
    for i, step in enumerate(state.steps, 1):
        icon = icons.get(step.status, "●")
        output = ""
        if step.output_data and step.output_data.get("output"):
            output = str(step.output_data["output"])[:120]
        elif step.error:
            output = f"[red]{step.error[:80]}[/red]"
        table.add_row(
            str(i),
            step.action_type.value if hasattr(step.action_type, 'value') else str(step.action_type),
            f"{icon} {step.status}",
            step.description[:60] + ("\n" + output if output else ""),
        )
    console.print(table)

    # ── Result ────────────────────────────────────────────────────────────
    if state.result:
        console.print(Panel(f"[bold green]Result[/bold green]\n\n{state.result}", expand=False))

    if state.error:
        console.print(Panel(f"[bold red]Error[/bold red]\n\n{state.error}", expand=False))

    # ── Verification ─────────────────────────────────────────────────────
    if state.verification_passed is not None:
        v_icon = "✅" if state.verification_passed else "❌"
        console.print(f"\n{v_icon} Verification: [{'green' if state.verification_passed else 'red'}]{'PASSED' if state.verification_passed else 'FAILED'}[/]")
        if state.verification_notes:
            console.print(f"[dim]{state.verification_notes[:200]}[/dim]")

    # ── Scratchpad ────────────────────────────────────────────────────────
    if verbose and state.scratchpad:
        console.print("\n[bold]Agent Scratchpad:[/bold]")
        for note in state.scratchpad:
            console.print(f"  [dim]• {note}[/dim]")

    return 0 if state.status == TaskStatus.COMPLETED else 1


@app.command()
def demo():
    """Run a quick demo with the mock company app (must be running)."""
    demo_task = (
        "Find the latest invoice from Acme Supplies Ltd. "
        "Extract the invoice number, total amount, and due date. "
        "Store these in memory and return a summary."
    )
    console.print("[bold yellow]Running demo task…[/bold yellow]")
    console.print(f"[dim]{demo_task}[/dim]\n")

    ctx = typer.Context(run)
    run(task=demo_task, max_iter=10, verbose=True)


@app.command()
def serve():
    """Start both the API server and mock app (for development)."""
    import subprocess
    console.print("[bold cyan]Starting servers…[/bold cyan]")
    console.print("  API Server  → http://localhost:8000")
    console.print("  Mock App    → http://localhost:8001")
    console.print("  Frontend    → open frontend/index.html in browser")
    console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

    import threading
    import uvicorn
    from agent.config import config

    def run_mock():
        uvicorn.run("mock_app.app:app", host="0.0.0.0", port=8001, log_level="warning")

    def run_api():
        uvicorn.run("api.main:app", host="0.0.0.0", port=8000, log_level="info")

    t1 = threading.Thread(target=run_mock, daemon=True)
    t1.start()

    run_api()  # blocking — main thread


if __name__ == "__main__":
    app()
