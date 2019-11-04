# Sphinx configuration
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import datetime
import sys

from conformity.sphinx_ext.linkcode import create_linkcode_resolve

from pysoa import __version__


print(sys.path)

_year = datetime.date.today().year
_date = datetime.datetime.utcnow().strftime('%Y %B %d %H:%M UTC')

project = 'PySOA'
# noinspection PyCompatibility
copyright = f'{_year}, Eventbrite'
author = 'Eventbrite'
version = __version__
release = __version__

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.linkcode',
    'conformity.sphinx_ext.autodoc',
]
source_suffix = {
    '.rst': 'restructuredtext',
}
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

source_encoding = 'utf-8-sig'
master_doc = 'index'
# noinspection PyCompatibility
rst_epilog = f"""
Copyright © {_year} Eventbrite, freely licensed under `Apache License, Version 2.0
<https://www.apache.org/licenses/LICENSE-2.0>`_.

Documentation generated {_date}.
"""
primary_domain = 'py'
add_function_parentheses = True
add_module_names = True
language = 'en'

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'related_projects.html',
        'searchbox.html',
    ],
}

html_favicon = None  # TODO
html_short_title = 'PySOA'
html_static_path = ['_static']
html_theme = 'alabaster'
html_theme_options = {
    'fixed_sidebar': True,
    'github_button': True,
    'github_repo': 'pysoa',
    'github_user': 'eventbrite',
}
html_title = 'PySOA - Fast Python (micro)Services'
html_use_index = True

autodoc_default_options = {
    'exclude-members': '__weakref__, __attrs_attrs__, __attrs_post_init__, __dict__, __slots__, __module__, __eq__, '
                       '__ne__, __ge__, __gt__, __le__, __lt__, __hash__, __repr__, __abstractmethods__, '
                       '__orig_bases__, __parameters__, __annotations__',
    'members': True,
    'show-inheritance': True,
    'special-members': True,
    'undoc-members': True,
}
autodoc_inherit_docstrings = True
autodoc_member_order = 'alphabetical'
autodoc_typehints = 'signature'

linkcode_resolve = create_linkcode_resolve('eventbrite', 'pysoa', 'pysoa', __version__)
