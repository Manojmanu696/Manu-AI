import json

from app.services.watch_listings import parse_title


def test_public_listings_match_exact_title_and_region():
    def action(name, region, function, price):
        return {"expectsAcceptanceOf": {"offeredBy": {"name": name}, "eligibleRegion": {"name": region},
                                        "businessFunction": f"example#{function}", "price": price}}

    graph = {"@graph": [{
        "@type": "TVSeries", "@id": "https://www.justwatch.com/in/tv-show/example", "name": "Example",
        "dateCreated": "2020-01-01", "numberOfSeasons": 2, "image": {"@id": "#poster"},
        "containsSeason": [{"seasonNumber": 1, "numberOfEpisodes": 10}, {"seasonNumber": 2, "numberOfEpisodes": 12}],
        "potentialAction": [
            action("First", "IN", "ProvideService", 100), action("Second", "IN", "ProvideService", 0),
            action("Third", "IN", "LeaseOut", 50), action("Fourth", "IN", "Sell", 250),
            action("Overseas", "US", "ProvideService", 20),
        ],
    }, {"@id": "#poster", "contentUrl": "https://images.justwatch.com/poster/123/example.jpg"}]}
    html = '<script type="application/ld+json">' + json.dumps(graph) + '</script>'
    html += '<h3 class="heading">Runtime</h3><div><!----><div>44min</div></div>'
    result = parse_title(html, "Example", 2020, "tv", "IN")
    assert result["image_url"].endswith("/example.jpg")
    assert (result["seasons"], result["episodes"], result["episode_duration"]) == (2, 22, "44 min")
    assert [(p["name"], p["access"]) for p in result["providers"]] == [
        ("First", "Subscription"), ("Second", "Free"), ("Third", "Rent"), ("Fourth", "Buy"),
    ]
    assert parse_title(html, "Another title", 2020, "tv", "IN") == {}
    assert parse_title(html, "Example", 2021, "tv", "IN") == {}
    assert parse_title(html, "Example", 2020, "tv", "US") == {}
