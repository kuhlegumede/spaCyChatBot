import spacy
import random
import logging
import sys
import re

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from dotenv import TELEGRAM_TOKEN


# ===========================
# CONFIG
# ===========================

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ===========================
# LOAD SPACY ONCE
# ===========================

nlp = spacy.load("en_core_web_sm")


# ===========================
# Conversation States
# ===========================

STATE0 = 0


# ===========================
# SentenceTyper Class
# ===========================

class SentenceTyper(spacy.matcher.Matcher):
    """Determines the sentence type."""

    def __init__(self, vocab):
        super().__init__(vocab)

        self.add(
            "WH-QUESTION",
            [
                [
                    {
                        "IS_SENT_START": True,
                        "TAG": {"IN": ["WDT", "WP", "WP$", "WRB"]}
                    }
                ]
            ]
        )

        self.add(
            "YN-QUESTION",
            [
                [
                    {"IS_SENT_START": True, "TAG": "MD"},
                    {"POS": {"IN": ["PRON", "PROPN", "DET"]}}
                ],
                [
                    {"IS_SENT_START": True, "POS": "VERB"},
                    {"POS": {"IN": ["PRON", "PROPN", "DET"]}},
                    {"POS": "VERB"}
                ]
            ]
        )

        self.add(
            "INSTRUCTION",
            [
                [
                    {
                        "IS_SENT_START": True,
                        "TAG": "VB"
                    }
                ],
                [
                    {
                        "IS_SENT_START": True,
                        "LOWER": {"IN": ["please", "kindly"]}
                    },
                    {
                        "TAG": "VB"
                    }
                ]
            ]
        )

        self.add(
            "WISH",
            [
                [
                    {"IS_SENT_START": True, "TAG": "PRP"},
                    {"TAG": "MD"},
                    {
                        "POS": "VERB",
                        "LEMMA": {
                            "IN": [
                                "love",
                                "like",
                                "appreciate"
                            ]
                        }
                    }
                ],
                [
                    {"IS_SENT_START": True, "TAG": "PRP"},
                    {
                        "POS": "VERB",
                        "LEMMA": {
                            "IN": [
                                "want",
                                "need",
                                "require"
                            ]
                        }
                    }
                ]
            ]
        )

    def get_handler(self, doc):

        matches = super().__call__(doc)

        if matches:
            match_id, _, _ = matches[0]

            match_name = self.vocab.strings[match_id]

            if match_name == "WH-QUESTION":
                return wh_question_handler

            elif match_name == "YN-QUESTION":
                return yn_question_handler

            elif match_name == "WISH":
                return wish_handler

            elif match_name == "INSTRUCTION":
                return instruction_handler

        return generic_handler


# ===========================
# VerbFinder Class
# ===========================

class VerbFinder(spacy.matcher.DependencyMatcher):

    def __init__(self, vocab):

        super().__init__(vocab)

        self.add(
            "VERBPHRASE",
            [
                [
                    {
                        "RIGHT_ID": "node0",
                        "RIGHT_ATTRS": {
                            "DEP": "ROOT"
                        }
                    },
                    {
                        "LEFT_ID": "node0",
                        "REL_OP": ">>",
                        "RIGHT_ID": "node1",
                        "RIGHT_ATTRS": {
                            "POS": "VERB"
                        }
                    }
                ],
                [
                    {
                        "RIGHT_ID": "node0",
                        "RIGHT_ATTRS": {
                            "DEP": "ROOT"
                        }
                    }
                ]
            ]
        )

    def get_verbs(self, doc):

        matches = super().__call__(doc)

        if matches:

            _, token_ids = matches[0]

            return sorted(
                [
                    token_id
                    for token_id in token_ids
                    if doc[token_id].pos_ in ["VERB", "AUX"]
                ]
            )

        return []


# ===========================
# POV replacement dictionary
# ===========================

povs = {
    "I am": "you are",
    "I was": "you were",
    "I'm": "you're",
    "I'd": "you'd",
    "I've": "you've",
    "I'll": "you'll",

    "you are": "I am",
    "you were": "I was",
    "you're": "I'm",
    "you'd": "I'd",
    "you've": "I've",
    "you'll": "I'll",

    "I": "you",
    "my": "your",
    "your": "my",
    "yours": "mine",
    "you": "I",
    "me": "you"
}


povs_c = re.compile(
    r'\b({})\b'.format(
        '|'.join(
            re.escape(pov)
            for pov in sorted(
                povs,
                key=len,
                reverse=True
            )
        )
    ),
    re.IGNORECASE
)


def replace_pov(text):

    def replacer(match):

        original = match.group(0)

        replacement = povs.get(
            original.lower(),
            original
        )

        if original[0].isupper():
            return replacement.capitalize()

        return replacement

    return povs_c.sub(replacer, text)


# ===========================
# Response Handlers
# ===========================

def wh_question_handler(nlp, sentence, verbs_idxs):

    logger.debug("WH-QUESTION handler")

    reply = []

    if len(sentence) > 0:
        reply.append(sentence[0].text.lower())

    subjects = [
        chunk.text
        for chunk in sentence.noun_chunks
        if chunk.root.dep_ == "nsubj"
    ]

    if subjects:
        reply.append(subjects[0])

    if verbs_idxs:
        reply.append(
            " ".join(
                sentence[i].text.lower()
                for i in verbs_idxs
                if i < len(sentence)
            )
        )

    objects = [
        chunk.text
        for chunk in sentence.noun_chunks
        if chunk.root.dep_ in ["dobj", "obj"]
    ]

    if objects:
        reply.append(objects[0])

    text = replace_pov(
        " ".join(reply)
    )

    response = random.choice([
        "I don't know ",
        "I can't say "
    ])

    response += text

    response += random.choice([
        ", but I'll try to find out later.",
        ", maybe I can find that out.",
        ". I'll check and you can ask me again."
    ])

    return response


def yn_question_handler(nlp, sentence, verbs_idxs):

    logger.debug("YN-QUESTION handler")

    reply = []

    subjects = [
        chunk.text
        for chunk in sentence.noun_chunks
        if chunk.root.dep_ == "nsubj"
    ]

    if subjects:
        reply.append(subjects[0])

    if verbs_idxs:
        reply.append(
            " ".join(
                sentence[i].text.lower()
                for i in verbs_idxs
                if i < len(sentence)
            )
        )

    objects = [
        chunk.text
        for chunk in sentence.noun_chunks
        if chunk.root.dep_ in ["dobj", "obj"]
    ]

    if objects:
        reply.append(objects[0])

    text = replace_pov(
        " ".join(reply)
    )

    response = random.choice([
        "I don't know whether ",
        "I can't say if "
    ])

    response += text

    response += random.choice([
        " right now. Let me find out.",
        ". I need to think about this."
    ])

    return response


def wish_handler(nlp, sentence, verbs_idxs):

    logger.debug("WISH handler")

    reply = replace_pov(sentence.text)

    reply = random.choice([
        "Understood: ",
        "Got it: "
    ]) + reply

    reply += random.choice([
        " I'll see what I can do.",
        ""
    ])

    return reply


def instruction_handler(nlp, sentence, verbs_idxs):

    logger.debug("INSTRUCTION handler")

    reply = replace_pov(sentence.text)

    reply = random.choice([
        "Understood: ",
        "Got it: "
    ]) + reply

    reply += random.choice([
        " What do you think?",
        " Thanks for sharing."
    ])

    return reply


def generic_handler(nlp, sentence, verbs_idxs):

    logger.debug("GENERIC handler")

    return replace_pov(sentence.text)


# ===========================
# Create matchers once
# ===========================

sentence_typer = SentenceTyper(nlp.vocab)
verb_finder = VerbFinder(nlp.vocab)


# ===========================
# Telegram Handlers
# ===========================

async def banter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message or not update.message.text:
        return STATE0

    doc = nlp(update.message.text)

    replies = []

    for sentence in doc.sents:

        sentence_doc = sentence.as_doc()

        verbs_idxs = verb_finder.get_verbs(
            sentence_doc
        )

        handler = sentence_typer.get_handler(
            sentence_doc
        )

        response = handler(
            nlp,
            sentence,
            verbs_idxs
        )

        replies.append(response)

    reply = " ".join(replies)

    await update.message.reply_text(reply)

    return STATE0


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "Hi! I am your bot. How may I be of service?"
    )

    return STATE0


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "Thanks for the chat. I'll be off then!"
    )

    return ConversationHandler.END


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "Send me a message and I will respond."
    )

    return STATE0


# ===========================
# Main
# ===========================

def main():

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    conversation_handler = ConversationHandler(

        entry_points=[
            CommandHandler("start", start)
        ],

        states={
            STATE0: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    banter
                )
            ]
        },

        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("help", help_command)
        ]
    )

    application.add_handler(
        conversation_handler
    )

    logger.info("Bot is starting...")

    application.run_polling()


if __name__ == "__main__":
    main()
