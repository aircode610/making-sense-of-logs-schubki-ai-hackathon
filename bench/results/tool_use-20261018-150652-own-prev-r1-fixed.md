# Tool-use benchmark: own-prev-r1-fixed (4 questions)

| model | questions | first_ok | need_ok | facts | errors_per_q | calls_per_q | tokens_in_per_q | seconds_per_q | crashed |
|---|---|---|---|---|---|---|---|---|---|
| anthropic:claude-sonnet-5-5 | 4 | 1.0 | 1.0 | 0.429 | 0.0 | 11.2 | 294759 | 28.2 | 0 |

| id | model | first | first ok | need ok | facts | calls | errors | tools |
|---|---|---|---|---|---|---|---|---|
| O-1 | sonnet | top_patterns | 1 | 1 | 1/1 | 2 | 0 | top_patterns rollup |
| O-2 | sonnet | count_by | 1 | 1 | 1/2 | 4 | 0 | list_values count_by count_by describe_corpus |
| O-3 | sonnet | count_by | 1 | 1 | 1/2 | 18 | 0 | describe_corpus list_values list_values count_by count_by count_by count_by top_patterns top_patterns top_patterns top_patterns top_patterns top_patterns find_patterns find_patterns top_patterns co_occurrence similar_patterns |
| O-4 | sonnet | count_by | 1 | 1 | 0/2 | 21 | 0 | describe_corpus count_by count_by count_by count_by count_by count_by count_by count_by count_by top_patterns count_by count_by count_by count_by search_logs facet similar_patterns find_patterns count_by top_patterns |
