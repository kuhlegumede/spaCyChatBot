import spacy
import random
import logging
import sys
import re
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler

# ===========================
# CONFIG
# ===========================
TELEGRAM_TOKEN = "8278389425:AAEpQFnmumJlDyhBiP9wJ02of9J0G8mB5PE"

# Logging setup
logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# ===========================
# SentenceTyper Class
# ===========================
class SentenceTyper(spacy.matcher.Matcher):
    """Derived matcher meant for determining the sentence type"""
    def __init__(self, vocab):
        super().__init__(vocab)
        self.add("WH-QUESTION", [[{"IS_SENT_START": True, "TAG": {"IN": ["WDT", "WP", "WP$", "WRB"]}}]])
        self.add("YN-QUESTION",
                 [[{"IS_SENT_START": True, "TAG": "MD"}, {"POS": {"IN": ["PRON", "PROPN", "DET"]}}],
                  [{"IS_SENT_START": True, "POS": "VERB"}, {"POS": {"IN": ["PRON", "PROPN", "DET"]}}, {"POS": "VERB"}]])
        self.add("INSTRUCTION",
                 [[{"IS_SENT_START": True, "TAG": "VB"}],
                  [{"IS_SENT_START": True, "LOWER": {"IN": ["please", "kindly"]}}, {"TAG": "VB"}]])
        self.add("WISH",
                 [[{"IS_SENT_START": True, "TAG": "PRP"}, {"TAG": "MD"},
                   {"POS": "VERB", "LEMMA": {"IN": ["love", "like", "appreciate"]}}],
                  [{"IS_SENT_START": True, "TAG": "PRP"}, {"POS": "VERB", "LEMMA": {"IN": ["want", "need", "require"]}}]])

    def __call__(self, *args, **kwargs):
        matches = super().__call__(*args, **kwargs)
        if matches:
            match_id, _, _ = matches[0]
            if match_id == self.vocab["WH-QUESTION"]:
                return wh_question_handler
            elif match_id == self.vocab["YN-QUESTION"]:
                return yn_question_handler
            elif match_id == self.vocab["WISH"]:
                return wish_handler
            elif match_id == self.vocab["INSTRUCTION"]:
                return instruction_handler
        return generic_handler


# ===========================
# VerbFinder Class
# ===========================
class VerbFinder(spacy.matcher.DependencyMatcher):
    def __init__(self, vocab):
        super().__init__(vocab)
        self.add("VERBPHRASE",
                 [[{"RIGHT_ID": "node0", "RIGHT_ATTRS": {"DEP": "ROOT"}},
                   {"LEFT_ID": "node0", "REL_OP": "<<", "RIGHT_ID": "node1", "RIGHT_ATTRS": {"POS": "PART"}},
                   {"LEFT_ID": "node0", "REL_OP": ">", "RIGHT_ID": "node2", "RIGHT_ATTRS": {"POS": "VERB"}}],
                  [{"RIGHT_ID": "node0", "RIGHT_ATTRS": {"DEP": "ROOT"}},
                   {"LEFT_ID": "node0", "REL_OP": ">", "RIGHT_ID": "node1", "RIGHT_ATTRS": {"TAG": "MD"}}],
                  [{"RIGHT_ID": "node0", "RIGHT_ATTRS": {"DEP": "ROOT"}}]])

    def __call__(self, *args, **kwargs):
        verbmatches = super().__call__(*args, **kwargs)
        if verbmatches:
            if len(verbmatches) > 1:
                logging.debug(f"NOTE: VerbFinder found {len(verbmatches)} matches.")
                for verbmatch in verbmatches:
                    logging.debug(verbmatch)
            match_id, token_idxs = verbmatches[0]
            return sorted(token_idxs)


# ===========================
# POV replacement dictionary
# ===========================
povs = {
    "I am": "you are", "I was": "you were", "I'm": "you're", "I'd": "you'd", "I've": "you've", "I'll": "you'll",
    "you are": "I am", "you were": "I was", "you're": "I'm", "you'd": "I'd", "you've": "I've", "you'll": "I'll",
    "I": "you", "my": "your", "your": "my", "yours": "mine", "you": "I", "me": "you",
}
povs_c = re.compile(r'\b({})\b'.format('|'.join(re.escape(pov) for pov in povs)))


# ===========================
# Handlers
# ===========================
def wh_question_handler(nlp, sentence, verbs_idxs):
    logging.debug("WH-QUESTION handler")
    reply = []
    reply.append(sentence[0].text.lower())
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'nsubj']
    if part: reply.append(part[0])
    reply.append(" ".join([sentence[i].text.lower() for i in verbs_idxs]))
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'dobj']
    if part: reply.append(part[0])
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), " ".join(reply))
    reply = random.choice(["I don't know ", "I can't say "]) + reply
    reply += random.choice([", but I'll try to find out later.",
                            ", maybe I can find that out. Remind me if I forget.",
                            ". I'll check and you can ask me again."])
    return reply


def yn_question_handler(nlp, sentence, verbs_idxs):
    logging.debug("YN-QUESTION handler")
    reply = []
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'nsubj']
    if part: reply.append(part[0])
    reply.append(" ".join([sentence[i].text.lower() for i in verbs_idxs]))
    part = [chunk.text for chunk in sentence.noun_chunks if chunk.root.dep_ == 'dobj']
    if part: reply.append(part[0])
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), " ".join(reply))
    reply = random.choice(["I don't know whether ", "I can't say if "]) + reply
    reply += random.choice([" right now. Let me find out.",
                            ". I need to think about this."])
    return reply


def wish_handler(nlp, sentence, verbs_idxs):
    logging.debug("WISH handler")
    reply = sentence.text
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), reply)
    reply = random.choice(["Understood: ", "Got it: "]) + reply
    reply += random.choice([" I'll see what I can do.", ""])
    return reply


def instruction_handler(nlp, sentence, verbs_idxs):
    logging.debug("INSTRUCTION handler")
    reply = sentence.text
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), reply)
    reply = random.choice(["Understood: ", "Got it: "]) + reply
    reply += random.choice([" What do you think?", " Thanks for sharing."])
    return reply


def generic_handler(nlp, sentence, verbs_idxs):
    logging.debug("GENERIC handler")
    reply = sentence.text
    reply = re.sub(povs_c, lambda match: povs.get(match.group()), reply)
    return reply


# ===========================
# Telegram Handlers
# ===========================
async def banter(update, context):
    nlp = spacy.load('en_core_web_sm')
    doc = nlp(update.message.text)
    sentencetyper = SentenceTyper(nlp.vocab)
    verbfinder = VerbFinder(nlp.vocab)

    reply = ''
    for sentence in doc.sents:
        verbs_idxs = verbfinder(sentence.as_doc())
        reply += (sentencetyper(sentence.as_doc()))(nlp, sentence, verbs_idxs)

    await update.message.reply_text(reply)
    return


async def state0_handler(update, context):
    if update.message.text.endswith('?'):
        await update.message.reply_text(random.choice([
            "Why do you ask?",
            "What do you think?",
            "That's a good question. How would you answer?",
        ]))
    else:
        await update.message.reply_text(random.choice([
            "Oh, I see. Tell me why that is.",
            "Alright. Please go on...",
            "I understand. And so?",
        ]))
    return 'STATE0'


async def start(update, context):
    await update.message.reply_text("Hi! I am your bot. How may I be of service?")
    return 'STATE0'


async def cancel(update, context):
    await update.message.reply_text("Thanks for the chat. I'll be off then!")
    return ConversationHandler.END


async def help(update, context):
    await update.message.reply_text("The help needs to go here.")
    return


# ===========================
# Main
# ===========================
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler(['start'], start)],
        states={
            'STATE0': [MessageHandler(filters.TEXT & ~filters.COMMAND, state0_handler)],
            'BANTER': [MessageHandler(filters.TEXT & ~filters.COMMAND, banter)],
        },
        fallbacks=[CommandHandler(['cancel'], cancel),
                   CommandHandler('help', help)]
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == '__main__':
    main()
