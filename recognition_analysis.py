"""Class-agnostic diagnostics and decisions; no training framework required."""
import hashlib
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, f1_score


def temperature_probabilities(probabilities, temperature=1.):
    logits = np.log(np.clip(probabilities, 1e-8, 1)) / float(temperature)
    logits -= logits.max(axis=-1, keepdims=True)
    result = np.exp(logits)
    return result / result.sum(axis=-1, keepdims=True)


def fit_temperature(probabilities, targets):
    values = (.5, .75, 1., 1.25, 1.5, 2., 3.)
    losses = [float(-np.log(np.clip(temperature_probabilities(probabilities, t)[np.arange(len(targets)), targets], 1e-8, 1)).mean()) for t in values]
    return float(values[int(np.argmin(losses))])


def accepted_mask(probabilities, policy, allowed=None, strict=False):
    p = np.atleast_2d(probabilities)
    predicted = p.argmax(axis=1)
    thresholds = np.array([policy.get('classes', {}).get(str(int(i)), {}).get('threshold', policy.get('threshold', .85)) for i in predicted])
    margins = np.array([policy.get('classes', {}).get(str(int(i)), {}).get('margin', policy.get('margin', .15)) for i in predicted])
    if strict: thresholds = np.maximum(thresholds, .95)
    ordered = np.sort(p, axis=1)
    accepted = (ordered[:, -1] >= thresholds) & (ordered[:, -1]-ordered[:, -2] >= margins)
    if allowed is not None: accepted &= np.asarray(allowed, bool)
    return accepted


def calibrate_policy(probabilities, targets, allowed):
    """No viable class threshold means reject that class, never a forced guess."""
    p = np.asarray(probabilities); predicted = p.argmax(axis=1)
    policy = {'threshold': .95, 'margin': .25, 'classes': {}, 'source': 'validation'}
    for i in range(p.shape[1]):
        choices = []
        for threshold in (.7, .8, .85, .9, .95, .98):
            for margin in (.1, .15, .25, .4):
                mask = accepted_mask(p, {'threshold': threshold, 'margin': margin}, allowed) & (predicted == i)
                n = int(mask.sum()); correct = int(np.sum(targets[mask] == i))
                if n >= 3 and correct / n >= .95:
                    choices.append((n, correct/n, threshold, margin))
        chosen = max(choices, default=(0, 0, 1.01, 1.01))
        policy['classes'][str(i)] = dict(threshold=chosen[2], margin=chosen[3], validation_accepted=chosen[0], supported=bool(choices))
    return policy


def confusion_analysis(matrix, labels):
    matrix = np.asarray(matrix, int); totals = matrix.sum(axis=1)
    pairs=[]; adjacency={i:set() for i in range(len(labels))}
    for i in range(len(labels)):
        for j in range(i+1,len(labels)):
            count=int(matrix[i,j]+matrix[j,i])
            if not count: continue
            forward=float(matrix[i,j]/max(1,totals[i])); backward=float(matrix[j,i]/max(1,totals[j]))
            pairs.append({'a':labels[i]['id'],'b':labels[j]['id'],'a_text':labels[i]['text'],'b_text':labels[j]['text'],
                          'a_to_b':int(matrix[i,j]),'b_to_a':int(matrix[j,i]),'a_rate':forward,'b_rate':backward,'errors':count})
            if max(forward,backward)>=.1:
                adjacency[i].add(j);adjacency[j].add(i)
    groups=[];seen=set()
    for start in adjacency:
        if start in seen or not adjacency[start]:continue
        stack=[start];group=[]
        while stack:
            i=stack.pop()
            if i in seen:continue
            seen.add(i);group.append(labels[i]['id']);stack.extend(adjacency[i]-seen)
        groups.append(group)
    return {'pairs':sorted(pairs,key=lambda r:(r['errors'],max(r['a_rate'],r['b_rate'])),reverse=True), 'groups':groups}


def evaluate(probabilities, targets, labels, policy=None, allowed=None):
    p=np.asarray(probabilities);y=np.asarray(targets);pred=p.argmax(axis=1)
    accepted=accepted_mask(p,policy or {},allowed);correct=pred==y
    matrix=confusion_matrix(y,pred,labels=np.arange(len(labels)))
    report=classification_report(y,pred,labels=np.arange(len(labels)),target_names=[l['id'] for l in labels],output_dict=True,zero_division=0)
    rows=[]
    for i,label in enumerate(labels):
        true=y==i;chosen=accepted & (pred==i)
        rows.append({**label,**report[label['id']], 'coverage':float(accepted[true].mean()) if true.any() else 0.,
                     'accepted_recall':float((accepted[true]&correct[true]).mean()) if true.any() else 0.,
                     'accepted_precision':float(correct[chosen].mean()) if chosen.any() else None,
                     'accepted':int(chosen.sum()),'false_positives':int((chosen&~correct).sum()),'rejected':int((true&~accepted).sum())})
    return {'accuracy':float(correct.mean()),'macro_f1':float(f1_score(y,pred,labels=np.arange(len(labels)),average='macro',zero_division=0)),
            'report':report,'by_class':rows,'confusion_matrix':matrix.tolist(), 'confusions':confusion_analysis(matrix,labels),
            'evaluated':len(y),'accepted':int(accepted.sum()),'rejected':int((~accepted).sum()),'coverage':float(accepted.mean()),
            'accepted_accuracy':float(correct[accepted].mean()) if accepted.any() else None,
            'false_accepts':int((accepted&~correct).sum()),'false_accept_rate':float((accepted&~correct).mean()),
            'unknown_false_accept_rate':None,'unknown_note':'No se han evaluado señas desconocidas reales.'}


def hard_weights(probabilities, targets):
    """Bounded emphasis on difficult training examples, equal total per class."""
    y=np.asarray(targets);p=np.asarray(probabilities)
    difficulty=1+np.minimum(2.,-np.log(np.clip(p[np.arange(len(y)),y],1e-5,1)))
    result=np.zeros(len(y),np.float32)
    for label in np.unique(y):
        mask=y==label
        result[mask]=difficulty[mask]/difficulty[mask].sum()*len(y)/len(np.unique(y))
    return result


def regression_check(candidate, previous, tolerance=.05):
    """Same evaluation examples required by caller. Check every retained class."""
    if previous is None:return {'comparable':False,'passed':False,'regressions':[]}
    old={r['id']:r for r in previous['by_class']};regressions=[]
    for row in candidate['by_class']:
        if row['id'] not in old:continue
        for key in ('recall','accepted_recall'):
            if row[key]+tolerance<old[row['id']][key]:
                regressions.append({'id':row['id'],'metric':key,'previous':old[row['id']][key],'candidate':row[key]})
    passed=not regressions and candidate['macro_f1']+tolerance>=previous['macro_f1'] and candidate['false_accept_rate']<=previous['false_accept_rate']+.01
    return {'comparable':True,'passed':passed,'regressions':regressions,'tolerance':tolerance}


def dataset_summary(raw, y, labels, groups, provenance):
    from capture_quality import sequence_quality
    rows=[]
    for i,label in enumerate(labels):
        indices=np.flatnonzero(y==i)
        low=sum(sequence_quality(raw[k])['low_quality'] for k in indices)
        n=len(indices);g=len(set(groups[indices]));recommend=[]
        if n<60:recommend.append('Reúne al menos 60 tomas variadas.')
        if g<3:recommend.append('Graba en al menos tres sesiones independientes.')
        if low:recommend.append('Revisa las tomas señaladas por mala calidad.')
        rows.append({**label,'samples':n,'groups':g,'low_quality':int(low),'recommendations':recommend})
    counts=np.bincount(y)
    return {'by_class':rows,'imbalance_ratio':float(counts.max()/counts.min()),'provenance':provenance}


def deduplicate(raw,y):
    seen={};keep=[]
    for i,p in enumerate(raw):
        digest=hashlib.sha256(p.tobytes()).hexdigest()
        if digest in seen:
            if y[seen[digest]]!=y[i]:raise ValueError('Ejemplos idénticos con etiquetas distintas: revisa el dataset.')
        else:seen[digest]=i;keep.append(i)
    return raw[keep],y[keep],len(raw)-len(keep)


def preprocessing_probe(raw, targets, train, validation):
    """Same fixed nearest-neighbor classifier; validation only, diagnostic ablation."""
    from sklearn.neighbors import KNeighborsClassifier
    from recognition_features import prepare_sequence, PREPROCESSING, FINGER_PREPROCESSING, DISCRIMINATIVE_PREPROCESSING
    output=[]
    for name in (PREPROCESSING,FINGER_PREPROCESSING,DISCRIMINATIVE_PREPROCESSING):
        features=np.stack([np.concatenate([np.mean(chunk,axis=0) for chunk in np.array_split(prepare_sequence(p,name),3)]) for p in raw])
        mean=features[train].mean(axis=0);scale=np.maximum(features[train].std(axis=0),.1)
        x=(features-mean)/scale
        model=KNeighborsClassifier(n_neighbors=min(3,len(train)),weights='distance').fit(x[train],targets[train])
        predicted=model.predict(x[validation])
        output.append({'preprocessing':name,'validation_accuracy':float(np.mean(predicted==targets[validation])),
                       'validation_macro_f1':float(f1_score(targets[validation],predicted,average='macro',zero_division=0))})
    return {'method':'3-NN, tres ventanas temporales; normalización ajustada solo con entrenamiento',
            'results':output,'note':'Sondeo diagnóstico de representación; no mide la precisión del modelo neuronal ni prueba una causa única.'}


def label_review_candidates(raw, targets, labels, train):
    """Review suggestions, not relabeling. Uses only training neighbors."""
    from sklearn.neighbors import NearestNeighbors
    from recognition_features import hand_descriptor
    descriptors=np.stack([hand_descriptor(raw[i],True) for i in train])
    if len(train)<4:return []
    _,neighbors=NearestNeighbors(n_neighbors=4).fit(descriptors).kneighbors(descriptors)
    rows=[]
    for j,indices in enumerate(neighbors):
        indices=[k for k in indices if k!=j][:3]
        votes=targets[train[indices]];counts=np.bincount(votes,minlength=len(labels));rival=int(counts.argmax())
        if rival!=targets[train[j]] and counts[rival]>=2:
            rows.append({'sha256':hashlib.sha256(raw[train[j]].tobytes()).hexdigest(),
                         'label':labels[targets[train[j]]]['id'],'neighbor_label':labels[rival]['id'],
                         'reason':'La geometría se parece a ejemplos de otra clase: revisar etiqueta y visibilidad, sin corrección automática.'})
    return rows
