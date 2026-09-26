===============
Developer guide
===============

For contributors and operators: how CalDART is built and how to work on it —
its architecture, a local development setup, configuration, and secrets, the
data model and HTTP API, the CMS and the design system, testing, and running
it in production.  The :doc:`/user/index` instead covers what each role can
do once the system is running; read that one if you are a member, a DART
leader, or an administrator rather than someone changing the code.

These pages are the specification.  They describe the system as it is, and
when a page and the code disagree, one of them is wrong — fix it in the same
pull request.  :doc:`architecture` is the map of how the pieces fit together.
Coding, testing, and documentation conventions live in the repository's
``CLAUDE.md`` and ``.claude/rules/``; read them before you write code.

New to the codebase?  :doc:`setup` gets it running, the
:doc:`/demo-walkthrough` shows you what it does, and :doc:`data-model` and
:doc:`api-reference` are the two references you will keep open after that.

.. toctree::
   :maxdepth: 1
   :caption: Foundations

   architecture
   setup
   configuration
   data-model
   api-reference
   api-system
   api-renewals

.. toctree::
   :maxdepth: 1
   :caption: Subsystems

   payments-setup
   cms
   theming
   reports
   reminders
   scheduled-reports
   renewals
   statements

.. toctree::
   :maxdepth: 1
   :caption: Extending

   extending

.. toctree::
   :maxdepth: 1
   :caption: Building and running

   local-development
   testing
   documentation
   deployment
   email
   backup-restore
   roadmap
