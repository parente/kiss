import click
import requests
import re
import tempfile
import atexit
import shutil
import subprocess

class AnyKiss(object):
    def search(self): 
        return True

def seq_to_regex(seq):
    if seq is None:
        return AnyKiss()
    pattern = ''.join(ch+'.*' for ch in ' '.join(seq).lower().split())
    return re.compile(pattern)

def get(path, *args, **kwargs):
    resp = requests.get('https://api.github.com/{}'.format(path.lstrip('/')), 
        *args, **kwargs)
    resp.raise_for_status()
    return resp

def get_kisses(gists, seq):
    regex = seq_to_regex(seq)
    kisses = []
    for gist in gists:
        description = gist['description'].lower()
        if description.startswith('kiss') and regex.search(description):
            kiss = dict(gist)
            kiss['name'] = gist['description'][4:].lstrip()
            kisses.append(kiss)
    return kisses

def show_kisses(kisses):
    for i, kiss in enumerate(kisses):
        click.echo('{}. {}'.format(i+1, kiss['name']))

def choose_kiss(kisses, prompt):
    while 1:
        value = click.prompt(prompt, type=int)
        if value > 0 and value <= len(kisses):
            return kisses[value-1]
        else:
            click.echo('Error: {} is not a valid choice'.format(value), err=True)

def cleanup_tmpdir(tmpdir):
    shutil.rmtree(tmpdir)

@click.group()
def cli():
    '''Keep It Simple Scripting'''
    pass

@cli.command()
@click.argument('seq', nargs=-1)
@click.option('--user', default='parente', help='GitHub account to search')
def ls(user, seq=None):
    '''Show all kisses.

    Optionally filters the list of kisses by the sequence of characters.
    '''
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    if not len(kisses):
        raise click.ClickException('No matching kisses')
    show_kisses(kisses)

@cli.command()
@click.argument('seq', nargs=-1)
@click.option('--user', default='parente', help='GitHub account to search')
def run(user, seq=None):
    '''Run a kiss.

    Prompts for which kiss to run if one is not matched by the optional sequence
    of characters.
    '''
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    if not len(kisses):
        raise click.ClickException('No matching kisses')
    if len(kisses) > 1:
        show_kisses(kisses)
        kiss = choose_kiss(kisses, 'Choose a kiss to run')
    else:
        kiss = kisses[0]
    
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
    '''Show kiss details.'''
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    if not len(kisses):
        raise click.ClickException('No matching kisses')
    if len(kisses) > 1:
        show_kisses(kisses)
        kiss = choose_kiss(kisses, 'Choose a kiss to view')
    else:
        kiss = kisses[0]
    click.echo('Showing details for "{}"\n'.format(kiss['name']))
    for filename in kiss['files']:
        if filename.startswith('README'):
            readme = requests.get(kiss['files'][filename]['raw_url'])
            click.echo(click.wrap_text(readme.text, preserve_paragraphs=True))
            break
    click.echo('\nIncludes: {}'.format(', '.join(kiss['files'])))
    click.echo('Created: {}'.format(kiss['created_at']))
    click.echo('Updated: {}'.format(kiss['updated_at']))
    click.echo('URL: {}'.format(kiss['html_url']))

@cli.command()
@click.argument('seq', nargs=-1)
@click.option('--user', default='parente', help='GitHub account to search')
def edit(user, seq):
    '''Clone a kiss to edit it.'''
    gists = get('users/{}/gists'.format(user)).json()
    kisses = get_kisses(gists, seq)
    if not len(kisses):
        raise click.ClickException('No matching kisses')
    if len(kisses) > 1:
        show_kisses(kisses)
        kiss = choose_kiss(kisses, 'Choose a kiss to edit')
    else:
        kiss = kisses[0]
