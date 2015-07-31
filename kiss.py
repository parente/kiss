import click
import requests
import re
import os
import tempfile
import atexit
import shutil
import subprocess
import json

CONFIG_PATH = os.path.expanduser('~/.config/kiss/config.json')

# Read config if available
if os.path.isfile(CONFIG_PATH):
    with open(CONFIG_PATH) as config_fh:
        CONFIG = json.load(config_fh)
else:
    CONFIG = {}

class AnyKiss(object):
    def search(self): 
        return True

def seq_to_regex(seq):
    '''
    Converts a sequence of characters to a regular expression that matches those
    characters in order with any number of characters in between.
    '''
    if seq is None:
        return AnyKiss()
    pattern = ''.join(ch+'.*' for ch in ' '.join(seq).lower().split())
    return re.compile(pattern)

def get(path, token=None):
    '''
    Does a GET against the GitHub API.
    '''
    headers = {}
    if token is not None:
        headers = {'Authorization': 'token ' + token}
    elif CONFIG:
        headers = {'Authorization': 'token ' + CONFIG['token']}

    resp = requests.get('https://api.github.com/{}'.format(path.lstrip('/')),
        headers=headers)
    resp.raise_for_status()
    return resp

def get_kisses(gists, seq):
    '''
    Turns a list of gists into a list of kisses containing the fuzzy sequence.
    '''
    regex = seq_to_regex(seq)
    kisses = []
    for gist in gists:
        description = gist['description'].lower()
        if description.startswith('kiss') and regex.search(description):
            kiss = dict(gist)
            kiss['name'] = gist['description'][4:].lstrip()
            kisses.append(kiss)
    if not len(kisses):
        raise click.ClickException('No matching kisses')
    return kisses

def get_one_kiss(kisses, prompt):
    if len(kisses) > 1:
        show_kisses(kisses)
        kiss = choose_kiss(kisses, prompt)
    else:
        kiss = kisses[0]
    return kiss

def show_kisses(kisses, start=1):
    '''
    Echoes a list of kisses numbered starting at the given value.
    '''
    for i, kiss in enumerate(kisses):
        click.echo('{}. {}'.format(i+start, kiss['name']))

def choose_kiss(kisses, prompt):
    '''
    Prompt the user to select a kiss from the list of kisses.
    '''
    while 1:
        value = click.prompt(prompt, type=int)
        if value > 0 and value <= len(kisses):
            return kisses[value-1]
        else:
            click.echo('Error: {} is not a valid choice'.format(value), err=True)

def get_username(user):
    user = CONFIG.get('username') if user is None else user
    if user is None:
        raise click.ClickException('Must provide GitHub username or login')
    return user

def cleanup_tmpdir(tmpdir):
    shutil.rmtree(tmpdir)

@click.group()
def cli():
    '''Keep It Simple Scripting'''
    pass

@cli.command()
@click.argument('seq', nargs=-1)
@click.option('--user', help='GitHub account to search')
def ls(user=None, seq=None):
    '''Show all kisses.

    Optionally filters the list of kisses by the sequence of characters.
    '''
    user = get_username(user)
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    if not len(kisses):
        raise click.ClickException('No matching kisses')
    show_kisses(kisses)

@cli.command()
@click.argument('seq', nargs=-1)
@click.option('--user', help='GitHub account to search')
def run(user=None, seq=None):
    '''Run a kiss.

    Prompts for which kiss to run if one is not matched by the optional sequence
    of characters.
    '''
    user = get_username(user)
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    kiss = get_one_kiss(kisses, 'Choose a kiss to run')
    
    tmpdir = tempfile.mkdtemp()
    atexit.register(cleanup_tmpdir, tmpdir)

    clone = subprocess.Popen(['git', 'clone', kiss['git_pull_url'], tmpdir], cwd=tmpdir)
    if clone.wait() > 0:
        raise click.ClickException('Failed to clone gist')
    
    chmod = subprocess.Popen(['chmod', '+x', './run'], cwd=tmpdir)
    if chmod.wait() > 0:
        raise click.ClickException('Failed to make run script executable')
    
    runner = subprocess.Popen(['./run'], cwd=tmpdir, universal_newlines=True)
    runner.wait()

@cli.command()
@click.argument('seq', nargs=-1)
@click.option('--user', default='parente', help='GitHub account to search')
def show(user, seq):
    '''Show kiss details.

    Prompts for which kiss to run if one is not matched by the optional sequence
    of characters.
    '''
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    kiss = get_one_kiss(kisses, 'Choose a kiss to view')

    click.echo('Showing details for "{}"\n'.format(kiss['name']))
    readme = None
    run = None
    for filename in kiss['files']:
        if filename.startswith('README'):
            readme = requests.get(kiss['files'][filename]['raw_url'])
        elif filename == 'run':
            run = requests.get(kiss['files'][filename]['raw_url'])
        if readme is not None and run is not None: break

    click.echo(click.wrap_text(readme.text, preserve_paragraphs=True))
    click.echo()
    click.echo(run.text)

    click.echo('\nIncludes: {}'.format(', '.join(kiss['files'])))
    click.echo('Created: {}'.format(kiss['created_at']))
    click.echo('Updated: {}'.format(kiss['updated_at']))
    click.echo('URL: {}'.format(kiss['html_url']))

@cli.command()
@click.argument('seq', nargs=-1)
@click.option('--user', default='parente', help='GitHub account to search')
def edit(user, seq):
    '''Clone a kiss to edit it.

    Prompts for which kiss to run if one is not matched by the optional sequence
    of characters.
    '''
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    kiss = get_one_kiss(kisses, 'Choose a kiss to edit')

    # TODO: edit

@cli.command()
@click.option('--user', help='GitHub username')
@click.option('--token_env', help='GitHub personal access token env var')
def login(user=None, token_env=None):
    '''
    Login to GitHub.

    Allows listing of secret gists and more requests per hour.
    '''
    if CONFIG:
        raise click.ClickException('Already logged in')
    if user is None:
        user = click.prompt('Github username')
    token = os.getenv(token_env)
    if token is None:
        token = click.prompt('Github personal access token', hide_input=True)

    try:
        get('users/{}/gists'.format(user), token=token)
    except requests.exceptions.HTTPError, e:
        if e.response.status_code == 401:
            raise click.ClickException('Invalid access token')
        else:
            raise e

    try:
        os.makedirs(os.path.dirname(CONFIG_PATH))
    except Exception:
        pass
    with open(CONFIG_PATH, 'w') as config_fh:
        json.dump(dict(username=user, token=token), config_fh)

    click.echo('Stored credentials in {}'.format(CONFIG_PATH))

@cli.command()
def logout():
    '''Logout from GitHub.'''
    if not CONFIG:
        raise click.ClickException('Not logged in')
    os.remove(CONFIG_PATH)
    click.echo('Removed credentials from {}'.format(CONFIG_PATH))

# 6ebdb1142d497f199535f6eb881c6d923a294e39