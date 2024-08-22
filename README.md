# Sublime Text 3 Syntax Highlighting for TLA+

This is a Sublime Text 3 package that defines syntax highlighting and other
niceties for [TLA+](https://lamport.azurewebsites.net/tla/tla.html).

## Installation

Clone this repo and copy it to your Sublime [packages
folder](https://www.sublimetext.com/docs/3/packages.html).  I hope to make this
available in [Package Control](https://packagecontrol.io/) eventually.

## What's Here

 - `tla.sublime-syntax`: [syntax definition](https://www.sublimetext.com/docs/3/syntax.html) (see also: [scope names](https://www.sublimetext.com/docs/3/scope_naming.html))
 - `symbols.tmPreferences`: [symbol navigation](http://docs.sublimetext.info/en/latest/reference/symbols.html)
 - `comments.tmPreferences`: [commenting rules](http://docs.sublimetext.info/en/latest/reference/comments.html)
 - `syntax_test_tla.tla`: [syntax highlighting test](https://www.sublimetext.com/docs/3/syntax.html#testing)
 - `tlapm.py`: plugin that invokes [`tlapm`](https://github.com/tlaplus/tlapm) and displays proof status

The tests are far from complete.  They do not all pass; you can put comments in
strange places to thwart the syntax highlighting rules.
