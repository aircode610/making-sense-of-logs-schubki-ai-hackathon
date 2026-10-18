# Tool-use benchmark: before-rescored (30 questions)

| model | questions | first_ok | need_ok | facts | errors_per_q | calls_per_q | tokens_in_per_q | seconds_per_q | crashed |
|---|---|---|---|---|---|---|---|---|---|
| anthropic:claude-opus-5-5 | 30 | 1.0 | 1.0 | 0.925 | 0.03 | 3.7 | 101694 | 21.2 | 0 |
| anthropic:claude-sonnet-5-5 | 30 | 0.967 | 1.0 | 0.83 | 0.0 | 4.1 | 97341 | 14.2 | 0 |

| id | model | first | first ok | need ok | facts | calls | errors | tools |
|---|---|---|---|---|---|---|---|---|
| T-B1 | opus | search_logs | 1 | 1 | 2/2 | 5 | 0 | search_logs get_context get_context pattern_history get_context |
| T-B2 | opus | search_logs | 1 | 1 | 3/3 | 4 | 0 | search_logs spread pattern_history search_logs |
| T-B3 | opus | top_patterns | 1 | 1 | 2/2 | 2 | 0 | top_patterns rollup |
| T-B4 | opus | priority_table | 1 | 1 | 1/1 | 3 | 0 | priority_table co_occurrence pattern_history |
| T-B5 | opus | top_patterns | 1 | 1 | 2/2 | 1 | 0 | top_patterns |
| T-B6 | opus | find_patterns | 1 | 1 | 2/2 | 7 | 0 | find_patterns precursors precursors search_logs get_context get_context get_context |
| T-B7 | opus | reliability_trend | 1 | 1 | 0/0 | 1 | 0 | reliability_trend |
| T-B8 | opus | whats_new | 1 | 1 | 2/2 | 2 | 0 | whats_new whats_new |
| T-O1 | opus | request_timeline | 1 | 1 | 2/2 | 2 | 0 | request_timeline search_logs |
| T-O2 | opus | value_outliers | 1 | 1 | 2/2 | 1 | 0 | value_outliers |
| T-O3 | opus | search_logs | 1 | 1 | 2/2 | 5 | 1 | search_logs count_by get_context get_context search_logs |
| T-O4 | opus | latency_profile | 1 | 1 | 2/2 | 2 | 0 | latency_profile list_values |
| T-S1 | opus | top_entities | 1 | 1 | 2/2 | 2 | 0 | top_entities search_logs |
| T-S2 | opus | search_logs | 1 | 1 | 3/3 | 5 | 0 | describe_corpus search_logs trend top_entities top_entities |
| T-S3 | opus | search_logs | 1 | 1 | 0/1 | 6 | 0 | search_logs periodicity facet heatmap periodicity trend |
| T-S4 | opus | priority_table | 1 | 1 | 1/1 | 7 | 0 | priority_table top_entities search_logs top_entities search_logs facet search_logs |
| T-Z1 | opus | priority_table | 1 | 1 | 2/2 | 5 | 0 | priority_table top_patterns pattern_history burst_timeline top_entities |
| T-Z2 | opus | search_logs | 1 | 1 | 2/2 | 3 | 0 | search_logs top_entities pattern_history |
| T-Z3 | opus | find_patterns | 1 | 1 | 1/1 | 2 | 0 | find_patterns co_occurrence |
| T-Z4 | opus | trend | 1 | 1 | 1/1 | 2 | 0 | trend facet |
| T-A1 | opus | priority_table | 1 | 1 | 2/2 | 4 | 0 | priority_table describe_corpus top_entities trend |
| T-A2 | opus | top_entities | 1 | 1 | 2/2 | 2 | 0 | top_entities search_logs |
| T-A3 | opus | search_logs | 1 | 1 | 2/2 | 3 | 0 | search_logs trend pattern_history |
| T-H1 | opus | search_logs | 1 | 1 | 2/2 | 4 | 0 | search_logs facet search_logs search_logs |
| T-H2 | opus | top_patterns | 1 | 1 | 1/1 | 5 | 0 | top_patterns count_by top_entities top_entities search_logs |
| T-H3 | opus | find_patterns | 1 | 1 | 2/2 | 5 | 0 | find_patterns precursors periodicity pattern_history burst_timeline |
| T-T1 | opus | count_by | 1 | 1 | 2/2 | 9 | 0 | count_by count_by count_by facet count_by rollup search_logs search_logs search_logs |
| T-T2 | opus | facet | 1 | 1 | 1/2 | 7 | 0 | facet search_logs top_patterns facet count_by count_by search_logs |
| T-T3 | opus | request_timeline | 1 | 1 | 1/2 | 2 | 0 | request_timeline search_logs |
| T-X1 | opus | count_by | 1 | 1 | 0/1 | 4 | 0 | count_by describe_corpus count_by count_by |
| T-B1 | sonnet | search_logs | 1 | 1 | 1/2 | 3 | 0 | search_logs get_context search_logs |
| T-B2 | sonnet | search_logs | 1 | 1 | 3/3 | 5 | 0 | search_logs spread trend search_logs search_logs |
| T-B3 | sonnet | top_patterns | 1 | 1 | 2/2 | 2 | 0 | top_patterns rollup |
| T-B4 | sonnet | priority_table | 1 | 1 | 1/1 | 7 | 0 | describe_corpus priority_table pattern_history search_logs facet burst_timeline trend |
| T-B5 | sonnet | top_patterns | 1 | 1 | 2/2 | 1 | 0 | top_patterns |
| T-B6 | sonnet | find_patterns | 1 | 1 | 2/2 | 6 | 0 | find_patterns search_logs precursors precursors get_context get_context |
| T-B7 | sonnet | reliability_trend | 1 | 1 | 0/0 | 2 | 0 | reliability_trend describe_corpus |
| T-B8 | sonnet | whats_new | 1 | 1 | 2/2 | 2 | 0 | whats_new whats_new |
| T-O1 | sonnet | request_timeline | 1 | 1 | 2/2 | 1 | 0 | request_timeline |
| T-O2 | sonnet | value_outliers | 1 | 1 | 1/2 | 1 | 0 | value_outliers |
| T-O3 | sonnet | search_logs | 1 | 1 | 2/2 | 5 | 0 | search_logs count_by get_context get_context get_context |
| T-O4 | sonnet | latency_profile | 1 | 1 | 1/2 | 2 | 0 | latency_profile list_values |
| T-S1 | sonnet | top_entities | 1 | 1 | 2/2 | 3 | 0 | describe_corpus top_entities search_logs |
| T-S2 | sonnet | search_logs | 1 | 1 | 2/3 | 6 | 0 | describe_corpus search_logs search_logs top_patterns trend trend |
| T-S3 | sonnet | find_patterns | 0 | 1 | 0/1 | 5 | 0 | describe_corpus find_patterns periodicity periodicity trend |
| T-S4 | sonnet | top_patterns | 1 | 1 | 1/1 | 13 | 0 | describe_corpus top_patterns top_entities priority_table search_logs facet top_entities search_logs search_logs search_logs count_by search_logs search_logs |
| T-Z1 | sonnet | top_patterns | 1 | 1 | 2/2 | 4 | 0 | top_patterns priority_table trend burst_timeline |
| T-Z2 | sonnet | search_logs | 1 | 1 | 2/2 | 3 | 0 | search_logs top_entities facet |
| T-Z3 | sonnet | find_patterns | 1 | 1 | 1/1 | 3 | 0 | find_patterns co_occurrence co_occurrence |
| T-Z4 | sonnet | trend | 1 | 1 | 1/1 | 1 | 0 | trend |
| T-A1 | sonnet | priority_table | 1 | 1 | 2/2 | 6 | 0 | describe_corpus priority_table top_patterns top_entities top_entities trend |
| T-A2 | sonnet | top_entities | 1 | 1 | 2/2 | 2 | 0 | top_entities search_logs |
| T-A3 | sonnet | search_logs | 1 | 1 | 2/2 | 3 | 0 | search_logs trend trend |
| T-H1 | sonnet | search_logs | 1 | 1 | 2/2 | 7 | 0 | search_logs facet search_logs search_logs search_logs search_logs search_logs |
| T-H2 | sonnet | top_patterns | 1 | 1 | 1/1 | 6 | 0 | top_patterns facet describe_corpus top_entities top_entities search_logs |
| T-H3 | sonnet | search_logs | 1 | 1 | 2/2 | 5 | 0 | search_logs find_patterns precursors trend burst_timeline |
| T-T1 | sonnet | count_by | 1 | 1 | 2/2 | 3 | 0 | count_by count_by rollup |
| T-T2 | sonnet | find_patterns | 1 | 1 | 1/2 | 10 | 0 | describe_corpus find_patterns facet search_logs search_logs top_patterns search_logs search_logs request_timeline search_logs |
| T-T3 | sonnet | search_logs | 1 | 1 | 0/2 | 1 | 0 | search_logs |
| T-X1 | sonnet | count_by | 1 | 1 | 0/1 | 4 | 0 | describe_corpus count_by count_by count_by |
