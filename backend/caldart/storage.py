"""The production static-file storage: whitenoise's, with no second hash on Vite's files.

whitenoise's ``CompressedManifestStaticFilesStorage`` renames every file ``collectstatic``
copies to carry a hash of its content, so the far-future cache headers it sends are safe.
Vite has already done that for its own build: every file under ``assets/`` carries a
content hash in its name, and the chunks import one another by those names.  A second
hash breaks that.  The template's ``<script>`` names the portal's entry by the manifest's
doubly hashed name while every lazy chunk imports it by Vite's, so the browser loads the
same module under two URLs, runs it twice, and mounts two React roots on
``#portal-root``; the first root's next update then fails with ``removeChild``.

This storage leaves every file under :data:`VITE_ASSETS_DIR` under the name Vite gave it,
still recorded in the manifest (as itself) and still compressed, and hashes every other
file exactly as whitenoise does.
"""

from __future__ import annotations

from django.core.files.base import File
from whitenoise.storage import CompressedManifestStaticFilesStorage

#: The directory Vite writes its build into (``build.assetsDir`` in
#: ``frontend/vite.config.ts``), as a static path prefix.  No installed app ships static
#: files under it (``backend/tests/test_static_storage.py`` checks).
VITE_ASSETS_DIR = "assets/"


class ViteManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """whitenoise's compressed manifest storage that does not rename Vite's build output.

    A file whose static path starts with :data:`VITE_ASSETS_DIR` keeps its name: the
    manifest maps it to itself and ``{% static %}`` and django-vite write it unchanged.
    Every other file is hashed as ``CompressedManifestStaticFilesStorage`` hashes it.
    """

    def hashed_name(
        self, name: str, content: File[bytes] | None = None, filename: str | None = None
    ) -> str:
        """Return ``name`` itself under the Vite directory, else the hashed name."""
        cleaned = name.replace("\\", "/")
        if cleaned.startswith(VITE_ASSETS_DIR):
            return cleaned
        return str(super().hashed_name(name, content, filename))
