"""Pure, vectorized analysis functions.

Every function takes the ``messages`` frame of a
:class:`~nostos.schema.Conversation` and returns a scalar or a tidy
:class:`polars.DataFrame`. Nothing here does I/O, printing or plotting, which
keeps the functions easy to test and reusable from a future web API.
"""

from nostos.analysis.activity import (
    WEEKDAYS,
    filter_keywords,
    messages_per_hour,
    messages_per_period,
    messages_per_sender,
    messages_per_weekday,
    messages_per_weekday_hour,
    top_periods,
)
from nostos.analysis.content import (
    average_words,
    average_words_per_month,
    average_words_per_sender,
    kind_counts,
    top_words,
    unique_word_count,
    word_frequencies,
    word_occurrences,
)
from nostos.analysis.responses import (
    BUCKETS,
    UNITS,
    mean_response_time,
    response_time_distribution,
    response_time_per_month,
    response_time_per_sender,
    response_time_summary,
    response_times,
)

__all__ = [
    "BUCKETS",
    "UNITS",
    "WEEKDAYS",
    "average_words",
    "average_words_per_month",
    "average_words_per_sender",
    "filter_keywords",
    "kind_counts",
    "mean_response_time",
    "messages_per_hour",
    "messages_per_period",
    "messages_per_sender",
    "messages_per_weekday",
    "messages_per_weekday_hour",
    "response_time_distribution",
    "response_time_per_month",
    "response_time_per_sender",
    "response_time_summary",
    "response_times",
    "top_periods",
    "top_words",
    "unique_word_count",
    "word_frequencies",
    "word_occurrences",
]
