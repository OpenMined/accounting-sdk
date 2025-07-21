"""Command line interface for the Accounting SDK.

This module provides CLI commands for interacting with the accounting service.
It supports user management and transaction operations.
"""

from typing import Optional
import click
from dotenv import load_dotenv
from colorama import init, Fore
from syft_accounting_sdk.core import UserClient
from syft_accounting_sdk.error import ServiceException


init()


@click.group()
def accounting() -> None:
    """Accounting SDK command line interface."""
    load_dotenv()


@accounting.group()
def user() -> None:
    """User management commands."""
    pass


def validate_url(
    ctx: click.Context, param: click.Parameter, value: Optional[str]
) -> str:
    """Validate the URL parameter.

    Args:
        ctx: Click context
        param: Click parameter
        value: URL value to validate

    Returns:
        Validated URL

    Raises:
        click.BadParameter: If URL is not provided
    """
    if value is None:
        raise click.BadParameter(
            "URL must be provided via --url or ACCOUNTING_SERVICE_URL environment variable"
        )
    return value.rstrip("/")


@user.command()
@click.option(
    "--url",
    envvar="ACCOUNTING_SERVICE_URL",
    callback=validate_url,
    help="Service URL (can be set via ACCOUNTING_SERVICE_URL env var)",
)
@click.option("--email", "-e", required=True, help="User's email address")
@click.option(
    "--password",
    "-p",
    help="Provide a password (if not provided, one will be generated)",
)
def add(url: str, email: str, password: Optional[str] = None) -> None:
    """Add a new user to the accounting system.

    Args:
        url: Service URL
        email: User's email address
        password: Optional password (generated if not provided)
    """
    try:
        user, pwd = UserClient.create_user(url=url, email=email, password=password)
        click.echo("Successfully added user:")
        click.echo(f"  email:    {Fore.YELLOW}{user.email}{Fore.RESET}")
        click.echo(
            f"  password: {Fore.YELLOW}{pwd}  {Fore.LIGHTYELLOW_EX}"
            "<- make sure you remember this, you can't see it later!"
            f"{Fore.RESET}"
        )
    except ServiceException as e:
        click.echo(f"{Fore.RED}Error: {e.message}{Fore.RESET}", err=True)
        raise click.Abort()
    except ValueError as e:
        click.echo(f"{Fore.RED}Error: {str(e)}{Fore.RESET}", err=True)
        raise click.Abort()
