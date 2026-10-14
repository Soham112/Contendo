"""Segments, business niches, their content pillars, and business tones.

This is the one place these lists live. The API validates against them and
serves them to the frontend (GET /niches); the pipeline reads a niche's pillars
from here. Nothing else in the backend or the frontend names a niche.

A pillar is a kind of post a business in that niche publishes. `needs` says
which facts a post of that kind is about. Those facts must come from the
author's own sources or input: a pillar never supplies them.
"""

from dataclasses import dataclass

SEGMENT_BUSINESS = "business"
SEGMENT_INDIVIDUAL = "individual"
SEGMENTS = (SEGMENT_BUSINESS, SEGMENT_INDIVIDUAL)

# The niche whose name the user types themselves (accounts.business_niche_other).
OTHER_NICHE = "other"


@dataclass(frozen=True)
class Pillar:
    key: str
    label: str
    about: str   # what a post of this kind does
    needs: str   # the facts it is about, which only the author can supply


@dataclass(frozen=True)
class Niche:
    key: str
    label: str
    pillars: tuple[Pillar, ...] = ()


@dataclass(frozen=True)
class Tone:
    key: str
    label: str


NICHES: tuple[Niche, ...] = (
    Niche("real_estate", "Real estate agent", (
        Pillar("new_listing", "New listing",
               "Announces a property that has just come to market.",
               "the property's area, type, features and price, and how to arrange a viewing"),
        Pillar("just_sold", "Just sold",
               "Marks a completed sale.",
               "the property's area and type, and whatever about the sale the author chooses to share"),
        Pillar("market_update", "Market update",
               "Explains what the local market is doing and what it means for buyers or sellers.",
               "the figures or trends, the area and period they cover, and where they come from"),
        Pillar("neighborhood_spotlight", "Neighborhood spotlight",
               "Shows what it is like to live in one area.",
               "the area and the places, amenities or character the author knows it for"),
        Pillar("buyer_seller_tips", "Buyer and seller tips",
               "Gives practical advice for buying or selling a home.",
               "the advice, and the author's experience or reasoning behind it"),
        Pillar("client_story", "Client story",
               "Tells how the author helped a client.",
               "what happened, told only with details the client has agreed to share"),
    )),
    Niche("dentist", "Dentist", (
        Pillar("oral_health_tips", "Oral health tips",
               "Gives patients practical advice on looking after their teeth.",
               "the advice, and the clinical reasoning behind it"),
        Pillar("treatment_explained", "Treatment explained",
               "Explains what a treatment involves and who it is for.",
               "the treatment, what it involves at this practice, and who it suits"),
        Pillar("meet_the_team", "Meet the team",
               "Introduces someone who works at the practice.",
               "the person, their role and what they have agreed to share about themselves"),
        Pillar("practice_news", "Practice news",
               "Shares news from the practice.",
               "what has changed: hours, equipment, services or people"),
        Pillar("common_questions", "Common questions",
               "Answers a question patients often ask.",
               "the question and the author's answer"),
        Pillar("patient_story", "Patient story",
               "Tells how the practice helped a patient.",
               "what happened, told only with details the patient has agreed to share"),
    )),
    Niche("restaurant", "Restaurant or café", (
        Pillar("menu_highlight", "Menu highlight",
               "Features one dish or drink.",
               "the dish, what is in it and when it is available"),
        Pillar("specials_and_events", "Specials and events",
               "Announces an offer or an event.",
               "what it is, the dates and times, and how to book"),
        Pillar("behind_the_scenes", "Behind the scenes",
               "Shows how the food is made or how the kitchen runs.",
               "the process, the people or the suppliers involved"),
        Pillar("meet_the_team", "Meet the team",
               "Introduces someone who works there.",
               "the person, their role and what they have agreed to share about themselves"),
        Pillar("local_community", "Local community",
               "Shows the business's part in its neighborhood.",
               "the event, partner or cause, and what the business did"),
        Pillar("guest_story", "Guest story",
               "Tells of an occasion a guest spent there.",
               "what happened, told only with details the guest has agreed to share"),
    )),
    Niche("salon_spa", "Salon or spa", (
        Pillar("service_spotlight", "Service spotlight",
               "Features one service or treatment.",
               "the service, what it involves and who it suits"),
        Pillar("care_tips", "Care tips",
               "Gives advice on looking after hair, skin or nails between visits.",
               "the advice, and the author's reasoning behind it"),
        Pillar("offers_and_availability", "Offers and availability",
               "Announces an offer or open appointments.",
               "the offer or the free slots, the dates, and how to book"),
        Pillar("meet_the_team", "Meet the team",
               "Introduces a stylist or therapist.",
               "the person, their speciality and what they have agreed to share about themselves"),
        Pillar("trends", "Trends",
               "Gives the author's view on a style or treatment trend.",
               "the trend and what the author makes of it"),
        Pillar("client_story", "Client story",
               "Tells of a result achieved for a client.",
               "what was done, told only with details the client has agreed to share"),
    )),
    Niche("home_services", "Home services", (
        Pillar("completed_job", "Completed job",
               "Shows a job the business has finished.",
               "the kind of job, the area, the problem and what was done"),
        Pillar("maintenance_tips", "Maintenance tips",
               "Gives homeowners advice on looking after their home.",
               "the advice, and the author's experience behind it"),
        Pillar("seasonal_reminder", "Seasonal reminder",
               "Reminds homeowners of work worth doing at this time of year.",
               "the work, why it matters now and what the business offers for it"),
        Pillar("service_explained", "Service explained",
               "Explains what a service involves and when it is needed.",
               "the service, what it involves and the signs that it is needed"),
        Pillar("meet_the_team", "Meet the team",
               "Introduces someone who works for the business.",
               "the person, their trade and what they have agreed to share about themselves"),
        Pillar("customer_story", "Customer story",
               "Tells how the business solved a customer's problem.",
               "what happened, told only with details the customer has agreed to share"),
    )),
    Niche("fitness_studio", "Fitness studio", (
        Pillar("class_spotlight", "Class spotlight",
               "Features one class or programme.",
               "the class, who it is for and when it runs"),
        Pillar("training_tips", "Training tips",
               "Gives practical advice on training or recovery.",
               "the advice, and the coach's reasoning behind it"),
        Pillar("schedule_and_offers", "Schedule and offers",
               "Announces timetable changes or an offer.",
               "what is changing or offered, the dates, and how to sign up"),
        Pillar("meet_the_coach", "Meet the coach",
               "Introduces a coach or instructor.",
               "the person, what they teach and what they have agreed to share about themselves"),
        Pillar("studio_community", "Studio community",
               "Shows the community around the studio.",
               "the event or occasion and who took part"),
        Pillar("member_story", "Member story",
               "Tells of a member's progress.",
               "what happened, told only with details the member has agreed to share"),
    )),
    Niche(OTHER_NICHE, "Other"),
)

NICHES_BY_KEY: dict[str, Niche] = {niche.key: niche for niche in NICHES}

TONES: tuple[Tone, ...] = (
    Tone("friendly", "Friendly and approachable"),
    Tone("professional", "Professional and reassuring"),
    Tone("upbeat", "Upbeat and energetic"),
    Tone("straightforward", "Straightforward and practical"),
    Tone("warm", "Warm and personal"),
)

TONES_BY_KEY: dict[str, Tone] = {tone.key: tone for tone in TONES}


def get_niche(key: str | None) -> Niche | None:
    """The niche with this key, or None when the key names no niche."""
    return NICHES_BY_KEY.get(key or "")


def options() -> dict:
    """The lists as the frontend needs them (GET /niches)."""
    return {
        "segments": list(SEGMENTS),
        "other_niche": OTHER_NICHE,
        "niches": [
            {
                "key": niche.key,
                "label": niche.label,
                "pillars": [{"key": p.key, "label": p.label, "about": p.about} for p in niche.pillars],
            }
            for niche in NICHES
        ],
        "tones": [{"key": tone.key, "label": tone.label} for tone in TONES],
    }
