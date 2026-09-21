"""Shared DRF pagination: ``?page=&page_size=``, default 25, max 200."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination, 25 results per page and a ``page_size`` cap of 200.

    A request may override the page size with ``?page_size=``, up to ``max_page_size``;
    a larger value is clamped rather than rejected.
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
