"""Wagtail page forms that hide the restricted blocks (PLAN §4.6).

``raw_html`` is "website_admin only".  Wagtail has no per-block permission, so
the page's ``base_form_class`` rebuilds the StreamField's block without the
restricted children when the editing user is not entitled to them.  Wagtail
hands the form the editing user as ``for_user``, which is the only hook that
knows both the user and the field.
"""

from __future__ import annotations

from wagtail.admin.forms import WagtailAdminPageForm
from wagtail.blocks import BlockWidget, StreamBlock

from apps.accounts.roles import WEBSITE_ADMIN
from apps.cms.blocks import RESTRICTED_BLOCK_TYPES


def can_use_raw_html(user) -> bool:
    """Only superusers and ``website_admin`` may paste unescaped HTML."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    has_role = getattr(user, "has_role", None)
    return bool(has_role and has_role(WEBSITE_ADMIN))


def _without_restricted_blocks(block: StreamBlock) -> StreamBlock:
    """A copy of ``block`` with every :data:`RESTRICTED_BLOCK_TYPES` child gone."""
    allowed = [
        (name, child)
        for name, child in block.child_blocks.items()
        if name not in RESTRICTED_BLOCK_TYPES
    ]
    return StreamBlock(allowed, required=block.meta.required)


class RestrictedBlocksPageForm(WagtailAdminPageForm):
    """Page form that strips restricted blocks for users who may not use them.

    Django deep-copies ``base_fields`` per form instance, so replacing the
    field's block and widget here affects this editing session only.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if can_use_raw_html(self.for_user):
            return
        for field in self.fields.values():
            block = getattr(field, "block", None)
            if not isinstance(block, StreamBlock):
                continue
            if not any(name in block.child_blocks for name in RESTRICTED_BLOCK_TYPES):
                continue
            restricted = _without_restricted_blocks(block)
            field.block = restricted
            field.widget = BlockWidget(restricted)
