:roles: system_admin

=======
Job log
=======

Each time the server runs one of its scheduled jobs, CalDART keeps a record of the run:
when it started, who started it, how it ended, and everything it wrote while it ran. The
job log shows those records, one job at a time, so you can tell from the website whether
last night's backup or this morning's renewal charges went well, and read why when they
did not. Only a system administrator sees it.


Opening a job's log
===================

Every job has a **View log** link beside a line that reads, for example, *Last run
10/15/2026 at 6:31 AM*, then how that run ended:

- each panel of :doc:`scheduled`, under what the job does;
- **Backups** on :doc:`health-database`, for the nightly backup (*Last nightly backup*);
- **FAA aircraft data** on the same page, for the nightly load (*Last nightly load*);
- the **Scheduled jobs** health check on :doc:`health-database`, beside each job it names.

A job that has not been run since the site began keeping these records reads *No run
recorded yet.* Its **View log** opens an empty log.

The site knows eight jobs, by these names:

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

The page is headed with the job's name and the word *log*, such as **Automatic renewal
charges log**. **Back to scheduled tasks**, or **Back to health and database** for the
backup and the FAA load, returns to the job's panel.

The table lists the job's runs newest first, 25 to a page, with **Previous** and **Next**
under it. A caption above it counts them, such as *30 runs*. Each row has:

- **Started**: the date and time the run began. Press it to open the run.
- **Started by**: *Server* for a run the server started on its schedule, or the name of the
  system administrator who started it with **Run now**.
- **Outcome**: a colored dot and a word. *Succeeded* and *Failed* say how a finished run
  ended. *Running* is a run still under way. *Stopped* is a run that is still marked as
  running long after it should have ended, which means the server stopped it, or restarted,
  partway through.
- **Duration**: how long the run took, such as *2 min 5 s*, or a dash while it runs.
- **Error**: the first line of a failed run's reason.

On a narrow screen the table leaves out **Error**, then **Started by**, then **Duration**,
and keeps **Started** and **Outcome** in sight.

The site keeps 90 days of runs. Older ones are deleted as new ones are recorded, and a job
that runs every minute, such as the bulk email sender, fills many pages in that time. The
server keeps its own copy of everything, for the person who installed the site.

Which runs are recorded
-----------------------

Every run the server starts on its schedule is recorded. So is a real run of the automatic
renewal charges, and an FAA data load, started with **Run now**: both run on the server
after the page answers, and each names who pressed the button. A practice run, and a real
run of any other job started with **Run now**, shows its result on its panel and is not
added to the log.


One run
=======

Opening a run shows its own page, headed with the job's name and *run*, such as
**Automatic renewal charges run**, with **Back to the Automatic renewal charges log** at
the top. It lists:

- **Started** and **Finished**, the date and time of each;
- **Duration** and **Started by**, as in the log;
- **Outcome**;
- **Exit status**: *0* for a run that succeeded, and another number for one that failed;
- **Options**, when the run was given any;
- **Error**: why a failed run failed, in the job's own words, such as *2 renewal charges
  need checking; settle them on the finance Renewals tab*.

Under them, **Output** shows everything the run wrote, in a fixed-width font, line for
line as the server printed it: the counts and the lines a job reports, and any warnings.
A run that wrote more than 64 KB keeps only its last 64 KB, and the page says so. A run
without any output says *The run didn't write anything.* A run that stopped on an
unexpected error also has a **Traceback**, the technical detail of where it stopped; copy
it whole to the person who installed the site.

The output can name members and their email addresses. Treat it as you would a member
record.


If something looks wrong
========================

The **Scheduled jobs** health check on :doc:`health-database` is the first place to look.
A job that failed, or stopped, reads there as a problem with its reason, and a job that has
not run when it should have reads as a warning.

- **Automatic renewal charges** fails every morning while any renewal charge waits for the
  treasurer to check it with the payment provider. Its error says how many. The treasurer
  settles them on the finance **Renewals** tab (:doc:`../finance/renewals`), and the next
  morning's run succeeds.
- A job that fails once and succeeds the next time needs nothing more. One that fails every
  time, or a job that has stopped running, needs the person who installed the site: send
  them the job's name, the run's time, and its **Error** and **Output**.
- Meanwhile **Run now** on the job's panel does the same work by hand.
