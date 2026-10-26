from agents.verification.normalizer import TextNormalizer
from agents.verification.simhash import hamming, simhash_bits, similarity
from fixtures import GOOD_REPORT, OFF_TOPIC_REPORT, PARAPHRASED_REPORT


def fp(text):
    return simhash_bits(TextNormalizer().lemmas(text), bits=64, k=3)


def test_identical_texts_have_zero_distance():
    assert hamming(fp(GOOD_REPORT), fp(GOOD_REPORT)) == 0


def test_small_edit_keeps_fingerprint_close():
    edited = GOOD_REPORT.replace("пять раз", "шесть раз") + " Дополнительно проверены отсортированные массивы."
    assert hamming(fp(GOOD_REPORT), fp(edited)) <= 10


def test_unrelated_texts_are_far():
    assert hamming(fp(GOOD_REPORT), fp(OFF_TOPIC_REPORT)) > 16


def test_paraphrase_is_not_a_duplicate():
    # перефразированный текст не должен попадать под порог дубликата —
    # его смысловую близость оценивает нейросетевой компонент, а не SimHash
    assert hamming(fp(GOOD_REPORT), fp(PARAPHRASED_REPORT)) > 10


def test_fingerprint_shape_and_similarity_bounds():
    bits = fp(GOOD_REPORT)
    assert len(bits) == 64 and set(bits) <= {0, 1}
    assert similarity(bits, bits) == 1.0
    assert simhash_bits([]) == [0] * 64
