# Questionnaire spec — source of truth: "Client questionnaire — Branding / Graphic Design — SEP 2026"
# (Client-questionnaire-Branding-_-Graphic-Design-2026.pdf). Same format as spec.py (see the notes there);
# images are Nourah's collages from the "supporting images" Dropbox folder, uploaded as gd-*.jpg.
#
# Additions to the PDF, needed to run it as a form:
#   * "About You" (brand name + contact) so the team knows who answered.
#   * Questions that only make sense for an existing brand are hidden when the client picks "New Brand":
#     01.2 (the PDF's "If you have an existing brand"), section 03, 07.2 and 08.1.
#   * 07.1 ends with an empty bullet in the PDF; it is offered as "Other" with a text box.

INTRO = [
    "Let’s make sure we’re starting from the same understanding. This short survey helps us understand what you need, how much you want to change, and what you expect from the project before we begin.",
]

SA = "Select all that apply:"
ONE = "Choose one:"
EXISTING = {"q": "01-1", "equals": "Existing Brand"}


def up_to(n):
    return "Choose up to %d:" % n


def pics(prefix, names):
    return [{"label": n, "img": "%s%s.jpg" % (prefix, n.lower().replace(" ", "-"))} for n in names]


SECTIONS = [
    {
        "num": "00", "title": "About You",
        "intro": "So we know who we’re working with.",
        "questions": [
            {"id": "00-1", "type": "text", "label": "Brand / Company Name", "field": "00.1 Brand / Company Name", "required": True},
            {"id": "00-2", "type": "text", "label": "Primary Contact", "field": "00.2 Primary Contact", "required": True,
             "placeholder": "Name, role and best way to reach you"},
        ],
    },
    {
        "num": "01", "title": "Where are you starting from?",
        "questions": [
            {"id": "01-1", "type": "single", "label": "Which best describes your project?", "field": "01.1 Starting point", "required": True,
             "options": [
                 {"label": "New Brand", "desc": "We are creating a new brand from the ground up"},
                 {"label": "Existing Brand", "desc": "We already have an established brand and want to work with or evolve what exists"},
             ]},
            {"id": "01-2", "type": "single", "img": True, "wide": True, "label": "What best describes what you are looking for?",
             "hint": ONE, "field": "01.2 Looking for", "show_if": EXISTING,
             "options": [
                 {"label": "Refine", "img": "gd-change-refine.jpg", "desc": "Small, focused improvements while keeping the existing identity largely intact"},
                 {"label": "Uplift", "img": "gd-change-uplift.jpg", "desc": "A noticeable refresh that makes the brand feel more current and polished, while remaining recognisably the same brand"},
                 {"label": "Adapt", "img": "gd-change-adapt.jpg", "desc": "Adjusting the existing identity for a new context, audience, market, product or purpose"},
                 {"label": "Explore", "img": "gd-change-explore.jpg", "desc": "Exploring a significantly different creative direction with more freedom to rethink the existing visual identity"},
                 {"label": "Not sure", "desc": "We would like Solid to help us determine the right level of change"},
             ]},
        ],
    },
    {
        "num": "02", "title": "Why are you doing this now?",
        "questions": [
            {"id": "02-1", "type": "multi", "label": "What prompted this project?", "hint": SA, "field": "02.1 What prompted this project",
             "options": ["The brand no longer feels current", "The brand has evolved", "We are targeting a new audience",
                         "We are entering a new market", "We are launching something new",
                         "The current identity is not being used consistently", "We want the brand to be perceived differently",
                         "We want to strengthen the existing identity", "Other"]},
            {"id": "02-2", "type": "textarea", "label": "Please tell us more about what changed or what you feel is missing:",
             "field": "02.2 What changed / what is missing", "rows": 4},
        ],
    },
    {
        "num": "03", "title": "What should change?", "show_if": EXISTING,
        "questions": [
            {"id": "03-1", "type": "single", "label": "How much change are you expecting?", "hint": ONE, "field": "03.1 Amount of change",
             "options": [
                 {"label": "Minimal", "desc": "I want the existing identity to remain almost entirely intact, with small improvements."},
                 {"label": "Noticeable", "desc": "I want the brand to feel clearly refreshed, but still recognisable."},
                 {"label": "Significant", "desc": "I am open to substantial changes to the visual identity."},
                 {"label": "Open", "desc": "I am open to exploring different directions before deciding how much should change."},
             ]},
            {"id": "03-2", "type": "multi", "label": "What would you like to keep from the current identity?", "hint": SA,
             "field": "03.2 Keep from current identity",
             "options": ["Logo / logo structure", "Colours", "Typography", "Graphic elements", "Overall visual character",
                         "Nothing specific", "Not sure"]},
            {"id": "03-3", "type": "multi", "label": "Is there anything you definitely want to move away from?", "hint": SA,
             "field": "03.3 Move away from",
             "options": ["Current colours", "Logo / logo structure", "Typography", "Graphic style", "Photography style",
                         "Overall visual character", "Nothing specific", "Not sure"]},
        ],
    },
    {
        "num": "04", "title": "How should the brand feel?",
        "questions": [
            {"id": "04-1", "type": "multi", "img": True, "wide": True, "label": "How would you like the brand to be perceived after this project?",
             "hint": up_to(5), "max": 5, "field": "04.1 Brand should feel",
             "options": pics("gd-feel-", ["Premium", "Modern", "Contemporary", "Bold", "Confident", "Minimal", "Refined",
                                          "Sophisticated", "Playful", "Approachable", "Warm", "Distinctive", "Innovative",
                                          "Timeless", "Energetic", "Authentic", "Luxurious", "Friendly", "Professional",
                                          "Expressive"]) + [{"label": "Other"}]},
            {"id": "04-2", "type": "multi", "img": True, "wide": True, "label": "How should it NOT feel?",
             "hint": up_to(3), "max": 3, "field": "04.2 Brand should NOT feel",
             "options": pics("gd-avoid-", ["Generic"]) + [{"label": "Dated"}]
                        + pics("gd-avoid-", ["Overly corporate", "Too playful", "Too minimal", "Too luxurious", "Too loud",
                                             "Too serious"]) + [{"label": "Too traditional"}]
                        + pics("gd-avoid-", ["Too trendy"]) + [{"label": "Other"}]},
        ],
    },
    {
        "num": "05", "title": "Who are we designing for?",
        "questions": [
            {"id": "05-1", "type": "multi", "label": "Who is the primary audience?", "hint": SA, "field": "05.1 Primary audience",
             "options": ["Existing customers", "New customers", "A younger audience", "A more premium audience",
                         "A broader audience", "A specific professional / business audience", "Internal / corporate audience",
                         "Other"]},
            {"id": "05-2", "type": "single", "label": "Is reaching a new or different audience part of this project?",
             "field": "05.2 New / different audience", "inline": True, "options": ["Yes", "No", "Not sure"]},
        ],
    },
    {
        "num": "06", "title": "References",
        "questions": [
            {"id": "06-1", "type": "single", "label": "Do you have any brands or visual references that represent a direction you like?",
             "field": "06.1 Has references", "inline": True, "options": ["Yes", "No"]},
            {"id": "06-1b", "type": "textarea", "label": "If yes, please share them with us.", "field": "06.1 References — links",
             "follow": True, "rows": 3, "show_if": {"q": "06-1", "equals": "Yes"},
             "upload": True, "files_field": "06.1 References — Files", "links_label": "Links (optional)",
             "help": "Upload files above, or paste links (websites, Instagram, Pinterest, Google Drive, Dropbox, WeTransfer…). Up to 50 MB per file."},
            {"id": "06-2", "type": "multi", "label": "What do you like about these references?", "hint": up_to(3), "max": 3,
             "field": "06.2 Liked about references", "show_if": {"q": "06-1", "equals": "Yes"},
             "options": ["Overall look & feel", "Packaging", "Colours", "Typography", "Photography", "Graphic language",
                         "Simplicity", "Level of detail", "Personality", "How distinctive the brand feels", "Other"]},
        ],
    },
    {
        "num": "07", "title": "What are you expecting from the project?",
        "questions": [
            {"id": "07-1", "type": "single", "label": "Which of the following best describes what you expect the final outcome to be?",
             "hint": ONE, "field": "07.1 Expected outcome", "stack": True,
             "options": ["Improvements to the existing identity", "A refreshed visual identity", "A new visual direction",
                         "A new brand identity", "A visual system that can be applied consistently",
                         "Not sure, I would like Solid to recommend the right outcome", "Other"]},
            {"id": "07-2", "type": "single", "label": "How would you describe your ideal outcome?", "hint": ONE,
             "field": "07.2 Ideal outcome", "stack": True, "show_if": EXISTING,
             "options": ["“It should still feel like us, just better”", "“It should clearly feel like an updated version of us”",
                         "“It should feel like us in a new context”", "“We are open to discovering what the brand could become”",
                         "“We are not sure yet”"]},
        ],
    },
    {
        "num": "08", "title": "Final Check",
        "questions": [
            {"id": "08-1", "type": "single", "label": "Which statement best reflects your expectation?", "hint": ONE,
             "field": "08.1 Expectation", "stack": True, "show_if": EXISTING,
             "options": ["I want minimal change and want the existing identity to remain largely intact",
                         "I want a noticeable refresh while keeping the brand recognisable",
                         "I want to adapt the existing identity for a new context or audience",
                         "I am open to a significantly different creative direction",
                         "I am not sure yet and would like Solid to help define the right direction"]},
            {"id": "08-2", "type": "textarea", "label": "Is there anything important you would like us to know before we begin?",
             "hint": "Optional", "field": "08.2 Anything else", "rows": 4},
        ],
    },
]
