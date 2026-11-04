"""Voto lineal opcional sobre la misma ventana que recibe la red temporal."""
import numpy as np
from config import FEATURE_DIM


def summary(sequences):
    x = np.asarray(sequences, dtype=np.float32)
    n, frames, _ = x.shape
    fingers = x[:, :, FEATURE_DIM:FEATURE_DIM + 158]
    shape = fingers.reshape(n, 3, frames // 3, 158).mean(axis=2)
    hands = x[:, :, FEATURE_DIM-126:FEATURE_DIM].reshape(n, frames, 2, 21, 3)
    tracks = hands[:, :, :, [0, 4, 8, 12, 16, 20], :2].reshape(n, 5, frames // 5, 24).mean(axis=2)
    return np.concatenate((shape.reshape(n,-1), np.diff(tracks, axis=1).reshape(n,-1)), axis=1)


def _probabilities(x, vote):
    logits = np.einsum('ij,kj->ik', summary(x), np.asarray(vote['weights'],np.float32))
    logits += np.asarray(vote['bias'],np.float32)
    exp = np.exp(logits - logits.max(axis=1,keepdims=True))
    return exp / exp.sum(axis=1,keepdims=True)


def combine(net, expert, threshold):
    mix = .25 * net + .75 * expert
    change = (expert.max(axis=1) >= threshold) & (mix.argmax(axis=1) != net.argmax(axis=1))
    return np.where(change[:,None], mix, net)


def apply_vote(x, probs, vote):
    if not vote:
        return probs
    single = np.ndim(probs) == 1
    out = combine(np.atleast_2d(probs), _probabilities(np.asarray(x).reshape(-1,*x.shape[-2:]),vote), vote['threshold'])
    return out[0] if single else out


def fit_vote(train, y, selection, targets, net):
    from sklearn.linear_model import LogisticRegression
    estimator = LogisticRegression(C=.3,class_weight='balanced',max_iter=350).fit(summary(train),y)
    weights, bias = estimator.coef_, estimator.intercept_
    if len(weights) == 1:  # sklearn representa dos clases mediante un único logit.
        weights = np.vstack((np.zeros_like(weights), weights))
        bias = np.r_[0.,bias]
    vote = {'weights':weights.tolist(),'bias':bias.tolist()}
    expert = _probabilities(selection,vote)
    before = net.argmax(axis=1)
    for cutoff in (.70,.75,.80,.85,.90,.95):
        after = combine(net, expert, cutoff).argmax(axis=1)
        repaired = (before != targets) & (after == targets)
        lost = (before == targets) & (after != targets)
        if repaired.sum() >= 3 and not lost.any():
            return {**vote,'threshold':cutoff,'selection_repaired':int(repaired.sum())}
    return None
