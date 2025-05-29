import click
from accountingSDK.core import UserClient
from dotenv import load_dotenv
from colorama import init, Fore

init()


@click.group()
def accounting():
    load_dotenv()


@accounting.group()
def user():
    pass


def validate_url(_, __, value):
    if value is None:
        raise click.BadParameter(
            "URL must be provided via --url or ACCOUNTING_SERVICE_URL environment variable"
        )
    return value


@user.command()
@click.option("--url", envvar="ACCOUNTING_SERVICE_URL", callback=validate_url)
@click.option("--email", "-e", required=True, help="user's email address")
@click.option(
    "--password",
    "-p",
    help="provide a password; if not, a random one will be generated",
)
def add(url, email, password):
    user, password = UserClient.create_user(url=url, email=email, password=password)
    print("successfully added user:")
    print(f"  email:    {Fore.YELLOW}{user.email}{Fore.RESET}")
    print(
        f"  password: {Fore.YELLOW}{password}  {Fore.LIGHTYELLOW_EX}<- make sure you remember this, you can't see it later!{Fore.RESET}"
    )
