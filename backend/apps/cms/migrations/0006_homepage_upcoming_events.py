"""Add the home page's calendar, which the sidebar shows the next few of.

Its own migration rather than a field added to 0004: that one has been applied
in checkouts already, and Django records a migration by name, so editing it
would leave those databases without the column.
"""

import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("cms", "0005_theme_follows_the_new_default")]

    operations = [
        migrations.AddField(
            model_name='homepage',
            name='upcoming_events',
            field=wagtail.fields.StreamField([('event', 4)], blank=True, block_lookup={0: ('wagtail.blocks.DateBlock', (), {}), 1: ('wagtail.blocks.CharBlock', (), {'max_length': 120}), 2: ('wagtail.blocks.CharBlock', (), {'help_text': 'Airport, town and time, or who it is for.', 'max_length': 120, 'required': False}), 3: ('wagtail.blocks.PageChooserBlock', (), {'help_text': 'The page with the details.', 'required': False}), 4: ('wagtail.blocks.StructBlock', [[('date', 0), ('title', 1), ('where', 2), ('page', 3)]], {})}, help_text='Dated events for the sidebar.  One that has passed stops showing.'),
        ),
    ]
