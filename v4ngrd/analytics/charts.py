import json
import os
import tempfile
import urllib.parse

from .. import config, tg


def quickchart_url(chart_config, width=800, height=400, bg_color="white"):
    encoded = urllib.parse.quote(json.dumps(chart_config))
    return f"{config.QUICKCHART_BASE}?c={encoded}&width={width}&height={height}&backgroundColor={bg_color}"


def fetch_chart(chart_config, width=800, height=400):
    url = quickchart_url(chart_config, width, height)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    ok = tg.download_file_via_url(url, path)
    return path if ok else None


def line_chart(labels, series, title):
    return {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [{"label": name, "data": values, "fill": False}
                         for name, values in series.items()],
        },
        "options": {"title": {"display": True, "text": title}},
    }


def bar_chart(labels, values, title, label="count"):
    return {
        "type": "bar",
        "data": {"labels": labels, "datasets": [{"label": label, "data": values}]},
        "options": {"title": {"display": True, "text": title}},
    }
