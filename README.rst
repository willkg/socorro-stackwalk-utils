======
README
======

What is this?
=============

This is a set of scripts and junk I use to compare versions of rust-minidump
minidump-stackwalk.

If you're not me, this is probably not helpful.

:Documentation: You're reading it!
:Bugs: https://github.com/willkg/socorro-stackwalk-compare/issues
:License: MPLv2


Set up
======

You'll need:

* rust--install it with `rustup <https://rustup.rs/>`_
* `crashstats-tools <https://github.com/willkg/crashstats-tools>`_
* make

To build ``minidump-stackwalk``, do::

    make build

To set the rust-minidump rev used, adjust the rev in the ``Makefile``.

If you want to use a Crash Stats API token, create a ``.env`` file with this in it::

    CRASHSTATS_API_TOKEN=yourtokenhere


Usage
=====

Generate a file of crashids::

    supersearch --num=100 > crashids.txt

Run that through ``rust_compare.sh``::

    rust_compare.sh $(cat crashids.txt)

Then read through the output.
