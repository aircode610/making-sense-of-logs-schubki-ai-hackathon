# Tool-use benchmark: own-prev-r2-fixed (4 questions)

| model | questions | first_ok | need_ok | facts | errors_per_q | calls_per_q | tokens_in_per_q | seconds_per_q | crashed |
|---|---|---|---|---|---|---|---|---|---|
| anthropic:claude-sonnet-5-5 | 4 | 1.0 | 1.0 | 0.571 | 0.0 | 9.5 | 321771 | 32.0 | 0 |

| id | model | first | first ok | need ok | facts | calls | errors | tools |
|---|---|---|---|---|---|---|---|---|
| O-1 | sonnet | top_patterns | 1 | 1 | 1/1 | 2 | 0 | top_patterns rollup |
| O-2 | sonnet | count_by | 1 | 1 | 1/2 | 4 | 0 | list_values count_by count_by describe_corpus |
| O-3 | sonnet | count_by | 1 | 1 | 1/2 | 17 | 0 | describe_corpus list_values list_values count_by count_by count_by top_patterns top_patterns top_patterns find_patterns find_patterns top_patterns top_patterns top_patterns top_patterns co_occurrence co_occurrence |
| O-4 | sonnet | count_by | 1 | 1 | 1/2 | 15 | 0 | describe_corpus count_by count_by count_by count_by top_patterns top_patterns top_patterns rollup find_patterns top_patterns top_patterns top_patterns find_patterns top_patterns |
