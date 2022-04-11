import click

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='1.0.0')
def stk():
    pass


@stk.command()
@click.argument('stack')
@click.argument('env')
#@click.option('--greeting', default='Hello', help='word to use for the greeting')
#@click.option('--caps', is_flag=True, help='uppercase the output')
def create(**kwargs):
    print(f"create {kwargs}")


if __name__ == '__main__':
    stk()
