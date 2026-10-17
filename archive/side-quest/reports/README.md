# Reports

| Experiment | Report (published, private to the owner's claude.ai account) | Source |
|---|---|---|
| 001 Hadoop minimal pipeline | https://claude.ai/artifact/8XPVMCUAX2aPirdtSeiUgE | [`001-hadoop.html`](001-hadoop.html) |
| 002 GAIA, three roles + Jev question design | https://claude.ai/artifact/FtbbRo9ZYvRXaXVX3vWagt | [`002-gaia.html`](002-gaia.html) |
| 002 Jev Field Guide (interactive demo deck for teams new to Jev) | https://claude.ai/artifact/LPRakghFXmQFkFWtKdfyw3 | [`002-jev-demo.html`](002-jev-demo.html), built by `experiments/002_gaia/build_demo.py` from `templates/002-jev-demo.template.html` |

The demo deck replays real recorded calls (exact requests, answers and latencies from `runs/002` dev traces); pages
cannot call Jev or Gemini live. To update it: edit the template, run the builder, republish `002-jev-demo.html`.

To view offline: `open reports/001-hadoop.html` (the pipeline diagram renders only on claude.ai).
To update the published page: edit the HTML and republish it to the same URL.
