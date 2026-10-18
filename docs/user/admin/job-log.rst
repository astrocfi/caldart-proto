:roles: system_admin

=======
Job log
=======

Each time the server runs one of its scheduled jobs, CalDART keeps a record of the run:
when it started, who started it, how it ended, and everything it wrote while it ran. The
job log shows those records, one job at a time. You can see from the website whether last
night's backup or this morning's renewal charges went well, and if they didn't, why. Only a
system administrator sees it.


Opening a job's log
===================

Every job has a **View log** link beside a line that says, for example, *Last run
10/15/2026 at 6:31 AM*, followed by how that run ended. You find these lines:

- in each panel of :doc:`scheduled`, under what the job does;
- under **Backups** on :doc:`health-database`, for the nightly backup (*Last nightly backup*);
- under **FAA aircraft data** on the same page, for the nightly load (*Last load*);
- in the **Scheduled jobs** health check on :doc:`health-database`, beside each job it names.

If a job hasn't run since the site started keeping these records, the line says *No run
recorded yet.* Its **View log** opens an empty log.

The site has eight jobs, with these names:

- **Nightly backup**, every night at 3:30 AM;
- **FAA aircraft data load**, every night at 4:30 AM;
- **Scheduled reports**, every morning at 6:00 AM;
- **Automatic renewal charges**, every morning at 6:30 AM;
- **Renewal reminder emails**, every morning at 7:00 AM;
- **Year-end statements**, on January 15th at 6:45 AM;
- **Bounce check**, every hour at twenty past;
- **Bulk email sender**, every minute.


What the log shows
==================

The page's heading is the job's name and the word *log*, such as **Automatic renewal
charges log**. **Back to scheduled tasks** takes you back to the job's panel. For the
backup and the FAA load, the link is **Back to health and database**.

The table lists the job's runs, newest first, 25 to a page, with **Previous** and **Next**
under it. A caption above it counts them, such as *30 runs*. **Show**, above the table,
picks *All runs* or *Failed runs* (the runs that failed or stopped). The page and the choice
stay in the page's address, so a run's **Back** link, or a bookmark, brings you back to the
same page. Each row has:

- **Started**: the date and time the run began. Press it to open the run.
- **Started by**: *Server* if the server started the run on its schedule, or the name of the
  system administrator who started it with **Run now**.
- **Outcome**: a colored dot and a word. *Succeeded* and *Failed* say how a finished run
  ended. If the server stopped a run at its time limit, it shows *Failed* with the error
  *Stopped by the server before it finished.* *Running* is a run still under way.
  *Stopped* is a run still marked as running long after it should have ended, which means
  the server restarted partway through.
- **Duration**: how long the run took, such as *2 min 5 s*, or a dash while it runs.
- **Error**: the first line of the reason a run failed.

On a narrow screen, the table drops **Error**, then **Started by**, then **Duration**, and
keeps **Started** and **Outcome** in sight.

The site keeps 90 days of runs, and deletes older ones as it records new ones. The bulk
email sender runs every minute. Of its runs that didn't find anything to send, the site
keeps only the newest, but it keeps every run that sent something. The server keeps its own
copy of everything, for the person who installed the site.

Which runs are recorded
-----------------------

The site records every run the server starts on its schedule. It also records every real
run started with **Run now** on a job's panel, under the name of whoever pressed it, so a
successful real run clears a failure from the **Scheduled jobs** health check. A practice
run doesn't change anything, and the site doesn't record it. If an automatic renewal run
finds another one already under way, it stops at once and isn't recorded either. The run
under way has its own record.


One run
=======

Opening a run takes you to its own page. The heading is the job's name and *run*, such as
**Automatic renewal charges run**, with **Back to the Automatic renewal charges log** at
the top. The page lists:

- **Started** and **Finished**, the date and time of each;
- **Duration** and **Started by**, as in the log;
- **Outcome**;
- **Exit status**: *0* if the run succeeded, and another number if it failed;
- **Options**, if the run was given any;
- **Error**: why the run failed, in the job's own words, such as *2 renewal charges
  need checking; settle them on the finance Renewals tab*.

Under them, **Output** shows everything the run wrote, in a fixed-width font, line for
line as the server printed it: the counts and lines the job reports, and any warnings. If a
run wrote more than 64 KB, only its last 64 KB is kept, and the page says so. If a run
didn't write any output, the page says *The run didn't write anything.* If a run stopped on
an unexpected error, the page also has a **Traceback**, the technical detail of where it
stopped. Copy the whole of it to the person who installed the site.

The output can name members and their email addresses. Treat it as you would a member
record.


If something looks wrong
========================

Look first at the **Scheduled jobs** health check on :doc:`health-database`. A job that
failed or stopped shows there as a problem, with its reason. A job that hasn't run when it
should have shows as a warning.

- **Automatic renewal charges** fails every morning while any renewal charge is waiting for
  the treasurer to check it with the payment service. Its error says how many are waiting.
  The treasurer settles them on the finance **Renewals** tab (:doc:`../finance/renewals`).
  The failure stays on the health check until the next run succeeds, either the next
  morning's run or a real **Run now** on :doc:`scheduled`.
- If a job fails once and succeeds the next time, you don't need to do anything more. If it
  fails every time, or has stopped running, tell the person who installed the site. Send
  them the job's name, the time of the run, and its **Error** and **Output**.
- In the meantime, **Run now** on the job's panel does the same work by hand.
