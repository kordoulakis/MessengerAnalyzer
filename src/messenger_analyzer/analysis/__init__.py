"""Pure, vectorized analysis functions.

Every function takes the ``messages`` frame of a
:class:`~messenger_analyzer.schema.Conversation` and returns a scalar or a tidy
:class:`polars.DataFrame`. Nothing here does I/O, printing or plotting, which
keeps the functions easy to test and reusable from a future web API.
"""

from messenger_analyzer.analysis.activity import (
    WEEKDAYS,
    filter_keywords,
    messages_per_hour,
    messages_per_period,
    messages_per_sender,
    messages_per_weekday,
    top_periods,
)
from messenger_analyzer.analysis.content import (
    average_words,
    average_words_per_month,
    average_words_per_sender,
    kind_counts,
    top_words,
    unique_word_count,
    word_frequencies,
    word_occurrences,
)
from messenger_analyzer.analysis.responses import (
    UNITS,
    mean_response_time,
    mean_response_time_per_month,
    mean_response_time_per_sender,
    response_times,
)

__all__ = [
    "UNITS",
    "WEEKDAYS",
    "average_words",
    "average_words_per_month",
    "average_words_per_sender",
    "filter_keywords",
    "kind_counts",
    "mean_response_time",
    "mean_response_time_per_month",
    "mean_response_time_per_sender",
    "messages_per_hour",
    "messages_per_period",
    "messages_per_sender",
    "messages_per_weekday",
    "response_times",
    "top_periods",
    "top_words",
    "unique_word_count",
    "word_frequencies",
    "word_occurrences",
]
