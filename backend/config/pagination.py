from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page numbering with a caller-settable size.

    The landing page asks for three products; the catalogue takes the default
    of 24. `max_page_size` is the point of the class: without it `?page_size=`
    would let any client ask for the entire table in a single query.
    """

    page_size_query_param = "page_size"
    max_page_size = 60
