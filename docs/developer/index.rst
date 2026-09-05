===============
Developer guide
===============

How CalDART is built and how to work on it: the authoritative plan, a local
development setup, configuration and secrets, the data model and HTTP API,
the CMS and the design system, testing, and running it in production.

:doc:`architecture` reproduces ``PLAN.rst`` in full and is the specification
every other page defers to.  If a page here and the plan disagree, one of them
is wrong — fix it in the same pull request.

New to the codebase?  :doc:`setup` gets it running, the
:doc:`../demo-walkthrough` shows you what it does, and :doc:`data-model` and
:doc:`api-reference` are the two references you will keep open after that.

.. toctree::
   :maxdepth: 1
   :caption: Foundations

   architecture
   setup
   configuration
   data-model
   api-reference

.. toctree::
   :maxdepth: 1
   :caption: Subsystems

   payments-setup
   cms
   theming
   reports
   reminders

.. toctree::
   :maxdepth: 1
   :caption: Building and running

   testing
   deployment
   backup-restore
   roadmap
