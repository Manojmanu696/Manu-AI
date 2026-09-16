"""Clearly marked sample data. Catalogue facts are intentionally conservative when offline."""
from .models import CatalogueItem, MediaItem, Memory

DEMO_MEDIA = [
    {"media_type":"movie","title":"Arrival","genres":"Science Fiction, Drama","personal_rating":9,"sentiment":"like","status":"completed","runtime":"116 min","release_year":2016,"description":"A linguist tries to understand visitors from another world.","tags":"thoughtful, first contact"},
    {"media_type":"movie","title":"The Prestige","genres":"Mystery, Thriller","personal_rating":9,"sentiment":"like","status":"completed","runtime":"130 min","release_year":2006,"description":"Two rival magicians take obsession to dangerous limits.","tags":"twisty, psychological"},
    {"media_type":"anime","title":"Monster","genres":"Psychological, Mystery","personal_rating":9,"sentiment":"like","status":"completed","runtime":"74 episodes","release_year":2004,"description":"A surgeon pursues the patient whose life he saved.","tags":"slow burn, moral ambiguity"},
    {"media_type":"anime","title":"Frieren: Beyond Journey's End","genres":"Fantasy, Drama","personal_rating":None,"sentiment":"neutral","status":"want","runtime":"28 episodes","release_year":2023,"description":"An elf mage reflects on friendship after an adventure ends.","tags":"reflective"},
    {"media_type":"tv","title":"Severance","genres":"Science Fiction, Thriller","personal_rating":8.5,"sentiment":"like","status":"current","runtime":"45 min episodes","release_year":2022,"description":"Workers split their work and home memories.","tags":"high concept, mystery"},
    {"media_type":"game","title":"Outer Wilds","genres":"Adventure, Mystery","personal_rating":10,"sentiment":"like","status":"completed","runtime":"16–20 hours","release_year":2019,"description":"Explore a handcrafted solar system caught in a time loop.","tags":"discovery, space"},
    {"media_type":"game","title":"Disco Elysium","genres":"RPG, Mystery","personal_rating":None,"sentiment":"neutral","status":"want","runtime":"25–40 hours","release_year":2019,"description":"A detective rebuilds himself while solving a murder.","tags":"writing, choices"},
    {"media_type":"book","title":"Piranesi","genres":"Fantasy, Mystery","personal_rating":8.5,"sentiment":"like","status":"completed","runtime":"272 pages","release_year":2020,"description":"A man lives in an infinite house of statues and tides.","tags":"atmospheric, uncanny"},
    {"media_type":"book","title":"Project Hail Mary","genres":"Science Fiction, Adventure","personal_rating":None,"sentiment":"neutral","status":"want","runtime":"496 pages","release_year":2021,"description":"A lone astronaut must save humanity.","tags":"science, space"},
]

# Offline demo entries include only reasonably stable descriptive metadata. Ratings/OTT are
# deliberately blank until a connected catalogue provider verifies them.
DEMO_CATALOGUE = [
    {"media_type":"movie","title":"Memento","genres":"Mystery, Psychological Thriller","tags":"twists, nonlinear, high payoff","runtime":"113 min","release_year":2000,"intensity":"High","ending_type":"Twist-driven","description":"A man with short-term memory loss hunts for the person who attacked his wife."},
    {"media_type":"movie","title":"The Invisible Guest","genres":"Mystery, Thriller","tags":"twists, fast-moving, closed room","runtime":"106 min","release_year":2016,"intensity":"High","ending_type":"Twist-driven","description":"A businessman wakes beside a dead body and must construct the truth."},
    {"media_type":"movie","title":"Coherence","genres":"Science Fiction, Mystery","tags":"high concept, dinner party, identity","runtime":"89 min","release_year":2013,"intensity":"Medium","ending_type":"Ambiguous","description":"A comet fractures the reality around a dinner party."},
    {"media_type":"movie","title":"Prisoners","genres":"Mystery, Thriller","tags":"moral ambiguity, investigation, dark","runtime":"153 min","release_year":2013,"intensity":"High","ending_type":"Resolved","description":"A desperate father and a detective confront a missing-child case."},
    {"media_type":"anime","title":"Steins;Gate","genres":"Science Fiction, Thriller","tags":"time travel, mystery, payoff","runtime":"24 episodes","episodes":24,"episode_duration":"24 min","release_year":2011,"intensity":"Medium","ending_type":"Resolved","description":"A group of friends accidentally discover a way to send messages through time."},
    {"media_type":"anime","title":"Odd Taxi","genres":"Mystery, Drama","tags":"tight plotting, urban mystery, payoff","runtime":"13 episodes","episodes":13,"episode_duration":"23 min","release_year":2021,"intensity":"Medium","ending_type":"Resolved","description":"A reserved taxi driver becomes entangled in a missing-girl case."},
    {"media_type":"anime","title":"Pluto","genres":"Science Fiction, Mystery","tags":"moral ambiguity, psychological, detective","runtime":"8 episodes","episodes":8,"episode_duration":"60 min","release_year":2023,"intensity":"Medium","ending_type":"Resolved","description":"A robot detective investigates a series of killings targeting the world's most advanced robots."},
    {"media_type":"anime","title":"Frieren: Beyond Journey's End","genres":"Fantasy, Drama","tags":"reflective, journey, character","runtime":"28 episodes","episodes":28,"episode_duration":"24 min","release_year":2023,"intensity":"Low","ending_type":"Ongoing","description":"An elf mage retraces an old journey and learns what friendship meant."},
    {"media_type":"tv","title":"Dark","genres":"Science Fiction, Mystery","tags":"time travel, family secrets, puzzle","runtime":"3 seasons","seasons":3,"episodes":26,"episode_duration":"45–60 min","release_year":2017,"intensity":"High","ending_type":"Resolved","description":"A missing child reveals a time-travel conspiracy spanning generations."},
    {"media_type":"tv","title":"Mr. Robot","genres":"Psychological Thriller, Drama","tags":"identity, paranoia, unreliable narrator","runtime":"4 seasons","seasons":4,"episodes":45,"episode_duration":"45–60 min","release_year":2015,"intensity":"High","ending_type":"Resolved","description":"A cyber-security engineer is recruited to bring down a powerful corporation."},
    {"media_type":"tv","title":"The Devil's Hour","genres":"Mystery, Thriller","tags":"time loop, psychological, short","runtime":"6 episodes","seasons":1,"episodes":6,"episode_duration":"55 min","release_year":2022,"intensity":"Medium","ending_type":"Ongoing","description":"A social worker wakes at the same strange hour and becomes connected to a serial killer."},
    {"media_type":"game","title":"Return of the Obra Dinn","genres":"Mystery, Puzzle","tags":"deduction, discovery, strong narrative","runtime":"8–12 hours","gameplay_style":"Deductive investigation","story_focus":"High","player_modes":"Single-player","difficulty":"Challenging","release_year":2018,"description":"Identify the fate of every crew member aboard a ghost ship."},
    {"media_type":"game","title":"The Case of the Golden Idol","genres":"Mystery, Puzzle","tags":"deduction, compact, twists","runtime":"6–8 hours","gameplay_style":"Point-and-click deduction","story_focus":"High","player_modes":"Single-player","difficulty":"Moderate","release_year":2022,"description":"Reconstruct a chain of strange deaths using only the scenes left behind."},
    {"media_type":"game","title":"Pentiment","genres":"Adventure, Mystery","tags":"historical, choices, writing","runtime":"15–20 hours","gameplay_style":"Narrative choices","story_focus":"High","player_modes":"Single-player","difficulty":"Low","release_year":2022,"description":"An artist investigates murders in a sixteenth-century Bavarian town."},
    {"media_type":"game","title":"Disco Elysium","genres":"RPG, Mystery","tags":"writing, choices, psychological","runtime":"25–40 hours","gameplay_style":"Dialogue-driven RPG","story_focus":"Very high","player_modes":"Single-player","difficulty":"Moderate","release_year":2019,"description":"A damaged detective rebuilds himself while solving a murder."},
    {"media_type":"book","title":"The 7½ Deaths of Evelyn Hardcastle","author":"Stuart Turton","genres":"Mystery, Science Fiction","tags":"body swap, twists, puzzle","page_count":512,"reading_length":"10–12 hours","runtime":"512 pages","release_year":2018,"intensity":"Medium","description":"A man relives the same day in different bodies to solve a murder."},
    {"media_type":"book","title":"Recursion","author":"Blake Crouch","genres":"Science Fiction, Thriller","tags":"memory, high concept, fast","page_count":336,"reading_length":"7–8 hours","runtime":"336 pages","release_year":2019,"intensity":"High","description":"A scientist and a detective confront a technology that rewrites memory and reality."},
    {"media_type":"book","title":"The Devotion of Suspect X","author":"Keigo Higashino","genres":"Mystery, Crime","tags":"cat and mouse, clever, compact","page_count":298,"reading_length":"6–7 hours","runtime":"298 pages","release_year":2005,"intensity":"Medium","description":"A brilliant mathematician engineers an alibi after a murder."},
    {"media_type":"book","title":"Project Hail Mary","author":"Andy Weir","genres":"Science Fiction, Adventure","tags":"science, space, problem solving","page_count":496,"reading_length":"11–13 hours","runtime":"496 pages","release_year":2021,"intensity":"Medium","description":"A lone astronaut wakes far from Earth with an impossible mission."},
]

DEMO_MEMORIES = [
    {"category":"favorite genres","content":"Psychological mysteries and smart science fiction.","source":"user"},
    {"category":"preferred pacing","content":"Likes deliberate stories when the payoff is meaningful.","source":"user"},
    {"category":"favorite themes","content":"Identity, moral ambiguity, discovery, and human connection.","source":"inferred","confidence":0.78},
]


def load_demo(db):
    changed = False
    if not db.query(MediaItem).filter_by(is_demo=True).first():
        for item in DEMO_MEDIA:
            db.add(MediaItem(**item, is_demo=True))
        for memory in DEMO_MEMORIES:
            db.add(Memory(**memory, is_demo=True))
        changed = True
    if not db.query(CatalogueItem).filter_by(is_demo=True).first():
        for item in DEMO_CATALOGUE:
            db.add(CatalogueItem(**item, is_demo=True))
        changed = True
    if changed:
        db.commit()
    return changed
