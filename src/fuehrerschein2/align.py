"""Align the known script to a self-recorded voiceover without speech recognition.

Speech is split into segments at pauses; a dynamic program assigns consecutive script words to the
segments so that each segment's duration matches its syllable count (preferring breaks at punctuation).
Inside a segment, word times are distributed by syllables.
"""
import json
import re
import sys

from script import SCENES

SPOKEN = {"3,5": "drei komma fünf", "0,5": "null komma fünf", "0,3": "null komma drei", "500": "fünfhundert",
          "1.000": "tausend", "21": "einundzwanzig", "THC": "te ha ze"}


def syl(tok):
    t = SPOKEN.get(tok.strip(".,:!?"), tok).lower()
    return max(1, len(re.findall(r"[aeiouäöüy]+", t)))


def tokens():
    out = []
    for si, sc in enumerate(SCENES):
        for tok in sc["text"].split():
            if tok == "–":
                continue
            out.append(dict(text=tok.strip(".,:!?"), raw=tok, scene=si, syl=syl(tok),
                            punct=tok[-1] in ".,:!?"))
    return out


def align(segs, toks):
    N, S = len(toks), len(segs)
    cum = [0]
    for t in toks:
        cum.append(cum[-1] + t["syl"])
    rate = sum(b - a for a, b in segs) / cum[-1]
    INF = 1e18
    for _ in range(2):
        f = [[INF] * (N + 1) for _ in range(S + 1)]
        bk = [[0] * (N + 1) for _ in range(S + 1)]
        f[0][0] = 0
        for i in range(1, S + 1):
            dur = segs[i - 1][1] - segs[i - 1][0]
            for j in range(i, N - (S - i) + 1):
                best, arg = INF, 0
                for k in range(max(i - 1, j - 40), j):
                    if f[i - 1][k] >= INF:
                        continue
                    sy = cum[j] - cum[k]
                    exp = rate * sy
                    c = ((dur - exp) / (exp + 0.35)) ** 2
                    last = toks[j - 1]
                    if not last["punct"]:
                        c += 0.25
                    if toks[k]["scene"] != last["scene"]:
                        c += 3.0  # never mix two chapters in one breath
                    v = f[i - 1][k] + c
                    if v < best:
                        best, arg = v, k
                f[i][j], bk[i][j] = best, arg
        # recover
        bounds, j = [], N
        for i in range(S, 0, -1):
            k = bk[i][j]
            bounds.append((k, j))
            j = k
        bounds.reverse()
        # refine rate
        rate = sum((segs[i][1] - segs[i][0]) for i in range(S)) / cum[-1]
    return bounds, rate, f[S][N]


if __name__ == "__main__":
    segs = json.load(open(sys.argv[1]))
    toks = tokens()
    bounds, rate, cost = align(segs, toks)
    words = []
    for (a, b), (s0, s1) in zip(bounds, segs):
        tot = sum(t["syl"] for t in toks[a:b])
        t = s0
        for tk in toks[a:b]:
            d = (s1 - s0) * tk["syl"] / tot
            words.append(dict(tk, start=t, end=t + d, seg=len([x for x in bounds if x[1] <= a])))
            t += d
        sps = tot / (s1 - s0)
        print(f"{s0:7.2f}-{s1:7.2f} {sps:4.1f} syl/s | " + " ".join(x["raw"] for x in toks[a:b]))
    print("cost", round(cost, 3), "rate", round(rate, 3))
    json.dump(words, open(sys.argv[2], "w"), ensure_ascii=False)
