import re
import nltk
from nltk import word_tokenize, sent_tokenize, pos_tag
from nltk import Tree
from nltk.corpus import stopwords
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import pandas as pd
import json

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')


class ProductTagger:
    def __init__(self):
        pass

    def remove_url(self, text):
        regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
        removed_url_text = re.sub(regex, "", text)
        return removed_url_text

    def remove_non_ascii(self, text):
        return re.sub(r'[^\x00-\x7F]+', ' ', text)

    def clean_text(self, text):
        text = self.remove_url(text)
        text = text.replace(":", "")
        text = text.replace("*", "")
        text = text.replace("&", "and")
        text = self.remove_non_ascii(text)
        return text

    def remove_keyword_from_text(self, text, keyword):
        # should also clean away channel's title !!
        # e.g., channel title: Olivia Loren The Makeup Princess #MYLIFEMYCHOICE, video_title: "KNOW THE DIFFERENCE BETWEEN SEX, GENDER, AND PRONOUNS!!||Olivia Loren The Makeup princess"
        hashtags = self.get_hashtags(keyword)
        for ht in hashtags:
            keyword = keyword.replace("#" + ht, "")
        keyword = keyword.strip()
        text = text.lower().replace(keyword.lower(), "")
        return text

    def get_sentences(self, text):
        IS_REMOVE_STOP_WORDS = True
        IS_REMOVE_COMMA = True
        sentences = []
        chunks = sent_tokenize(text)
        stop_words = set(stopwords.words('english'))
        for c in chunks:
            chunk_sentences = c.split("\n")
            for s in chunk_sentences:
                if not IS_REMOVE_STOP_WORDS:
                    sentences.append(s)
                    continue
                words = word_tokenize(s)
                filtered_words = []
                for w in words:
                    if w.lower() in stop_words:
                        continue
                    if IS_REMOVE_COMMA:
                        if w == ",":
                            continue
                    filtered_words.append(w)
                cleaned_sentence = " ".join(filtered_words)
                sentences.append(cleaned_sentence)
        return sentences

    def GetNPWithSyntaxRules(self, text):
        nounphrases = []
        words = nltk.word_tokenize(text)
        tagged = nltk.pos_tag(words)
        chunk_name_lst = ["NP"]
        grammar = r"""  NP:
                {<NN|NNS|NNP|NNPS><NN|VBZ|DT|JJ|JJS|JJR|NNS|NNP|NNPS|CC|VBD|RB>+<NN|NNS|NNP|NNPS>}
            """
        chunkParser = nltk.RegexpParser(grammar)
        tree = chunkParser.parse(tagged)
        for subtree in tree.subtrees(filter=lambda t: t.label() in chunk_name_lst):
            myPhrase = ''
            for item in subtree.leaves():
                myPhrase += ' ' + item[0]
            nounphrases.append(myPhrase.strip())
        nounphrases = list(filter(lambda x: len(x.split()) > 1, nounphrases))
        return nounphrases

    def get_hashtags(self, text):
        tags = set({tag.strip("#") for tag in text.replace(
            '#', ' #').split() if tag.startswith("#")})
        return list(tags)

    def get_noun_phrases_from_text(self, text, noun_phrases=[]):
        text = self.clean_text(text)
        sentences = self.get_sentences(text)
        for sentence in sentences:
            if sentence == "":
                continue
            sentence_noun_phrases = self.GetNPWithSyntaxRules(sentence)
            noun_phrases.extend(sentence_noun_phrases)
        return noun_phrases

    def get_words_of_interest_from_text(self, text):
        words_of_interest = []
        text = self.clean_text(text)
        sentences = self.get_sentences(text)
        for sentence in sentences:
            if sentence == "":
                continue
            words_of_interest.extend(
                self.get_words_of_interest_with_syntax_rules(sentence))
        return words_of_interest

    def get_words_of_interest_with_syntax_rules(self, text):
        words_of_interest = []
        words = nltk.word_tokenize(text)
        tagged = nltk.pos_tag(words)

        keep_pos_lst = ["NN", "NNP", "NNS", "NNPS", "JJ", "JJS", "JJR", "VBZ"]
        """ V3 - Avoid extracting singular words from a noun phrase """
        for i in range(len(tagged)):
            current_token = tagged[i][0]
            current_token_pos = tagged[i][1]
            if len(current_token) == 1 or current_token_pos not in keep_pos_lst:
                continue

            # final word among tokens
            if i == len(tagged) - 1 and i > 0:
                # get the word before it and check if it's also one of a keep_pos
                previous_token_pos = tagged[i - 1][1]
                if current_token_pos in keep_pos_lst and previous_token_pos in keep_pos_lst:
                    continue
            elif i < len(tagged) - 1:
                # get the word after it and check if it's also one of a keep_pos
                next_token_pos = tagged[i + 1][1]
                if current_token_pos in keep_pos_lst and next_token_pos in keep_pos_lst:
                    continue
            words_of_interest.append(current_token)

        chunk_name = "NP"
        rule = r""" NP:
              {<NN|NNS|NNP|NNPS>*<NN|VBZ|DT|JJ|JJS|JJR|NNS|NNP|NNPS|CC|VBD|RB>+<NN|NNS|NNP|NNPS>}
          """
        chunk_parser = nltk.RegexpParser(rule)
        tree = chunk_parser.parse(tagged)
        noun_phrases = []
        for subtree in tree.subtrees(filter=lambda t: t.label() == chunk_name):
            phrase = ''
            for item in subtree.leaves():
                phrase += ' ' + item[0]
            noun_phrases.append(phrase.strip())
        noun_phrases = list(filter(lambda x: len(x.split()) > 1, noun_phrases))
        words_of_interest.extend(noun_phrases)

        return words_of_interest

    def get_unique_words_of_interest(self, words_of_interest):
        unique_woi_in_lowercase = set()
        unique_woi = []
        for woi in words_of_interest:
            woi_in_lowercase = woi.strip().lower()
            if woi_in_lowercase not in unique_woi_in_lowercase:
                unique_woi_in_lowercase.add(woi_in_lowercase)
                unique_woi.append(woi)
        return unique_woi

    def get_product_categories_and_lexicon(self, filename):
        product_categories = {}
        with open(filename) as file:
            product_categories = json.load(file)
        product_categories_lexicon = []
        for cat in product_categories:
            product_categories_lexicon.extend(product_categories[cat])
            product_categories[cat] = set(product_categories[cat])
        return product_categories, product_categories_lexicon

    def categorize_product(self, product, product_categories, product_categories_lexicon):
        PRODUCT_CATEGORY_SIMILARITY_THRESHOLD = 85
        identified_product_categories = {}
        sum_of_product_categories_count = 0

        words_of_interest = []
        words_of_interest = self.get_words_of_interest_from_text(product)
        words_of_interest = self.get_unique_words_of_interest(words_of_interest)
        for woi in words_of_interest:
            woi_in_lowercase = woi.lower()
            woi_identified_product_categories = {}
            for l in product_categories_lexicon:
                lexicon_match = re.search(r'(?<!\S)\b' + l + r'(?![\w-])', woi_in_lowercase)
                if lexicon_match == None:
                    continue

                extracted_category = ""
                for cat in product_categories:
                    if l in product_categories[cat]:
                        extracted_category = cat
                        break

                if identified_product_categories.get(extracted_category) == None:
                    identified_product_categories[extracted_category] = 1
                    woi_identified_product_categories[extracted_category] = 1
                    sum_of_product_categories_count += 1
                elif woi_identified_product_categories.get(extracted_category) == None:
                    identified_product_categories[extracted_category] += 1
                    sum_of_product_categories_count += 1
                    woi_identified_product_categories[extracted_category] = 1

        for category in identified_product_categories:
            identified_product_categories[category] = (identified_product_categories[
                                                           category] / sum_of_product_categories_count) * 100
        identified_product_categories = dict(
            sorted(identified_product_categories.items(), key=lambda item: item[1], reverse=True))


        return {"identified_product_categories": identified_product_categories}