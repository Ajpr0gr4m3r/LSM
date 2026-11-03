"""Training-only objectives. Saved inference models contain standard Keras layers."""
import numpy as np
import tensorflow as tf
from recognition_analysis import hard_weights


class HardExampleSequence(tf.keras.utils.Sequence):
    def __init__(self, points, targets, batch_size=16, seed=42):
        self.points=points;self.targets=targets;self.y=targets.argmax(axis=1)
        self.batch_size=batch_size;self.rng=np.random.default_rng(seed)
        self.weights=hard_weights(np.ones_like(targets)/targets.shape[1],self.y)
        self.order=self.rng.permutation(len(points))
    def __len__(self):return int(np.ceil(len(self.points)/self.batch_size))
    def __getitem__(self,index):
        indices=self.order[index*self.batch_size:(index+1)*self.batch_size]
        return self.points[indices],self.targets[indices],self.weights[indices]
    def on_epoch_end(self):self.order=self.rng.permutation(len(self.points))


class MineHardExamples(tf.keras.callbacks.Callback):
    def __init__(self, sequence):super().__init__();self.sequence=sequence
    def on_epoch_end(self,epoch,logs=None):
        if epoch<2 or epoch%2:return
        p=np.concatenate([self.model(self.sequence.points[i:i+64],training=False).numpy() for i in range(0,len(self.sequence.points),64)])
        self.sequence.weights=hard_weights(p,self.sequence.y)
        if logs is not None:logs['mining_max_weight']=float(self.sequence.weights.max())


def supervised_contrastive_loss(labels,embeddings,temperature=.15):
    z=tf.math.l2_normalize(embeddings,axis=1)
    logits=tf.matmul(z,z,transpose_b=True)/temperature
    logits-=tf.stop_gradient(tf.reduce_max(logits,axis=1,keepdims=True))
    offdiag=1-tf.eye(tf.shape(z)[0])
    positives=tf.cast(tf.equal(labels[:,None],labels[None,:]),tf.float32)*offdiag
    logp=logits-tf.math.log(tf.reduce_sum(tf.exp(logits)*offdiag,axis=1,keepdims=True)+1e-8)
    counts=tf.reduce_sum(positives,axis=1)
    valid=counts>0
    losses=-tf.reduce_sum(logp*positives,axis=1)/tf.maximum(counts,1)
    return tf.math.divide_no_nan(tf.reduce_sum(tf.where(valid,losses,0)),tf.reduce_sum(tf.cast(valid,tf.float32)))


def contrastive_warmup(encoder,points,targets,epochs=4,seed=42):
    """Only train samples; two positives/class and at most eight classes/batch."""
    rng=np.random.default_rng(seed);classes=np.unique(targets)
    optimizer=tf.keras.optimizers.legacy.Adam(learning_rate=2e-4,clipnorm=1.)
    @tf.function
    def step(x,y):
        with tf.GradientTape() as tape:
            loss=supervised_contrastive_loss(y,encoder(x,training=True))
            if encoder.losses:loss+=tf.add_n(encoder.losses)
        grads=tape.gradient(loss,encoder.trainable_variables)
        optimizer.apply_gradients((g,v) for g,v in zip(grads,encoder.trainable_variables) if g is not None)
        return loss
    history=[]
    for epoch in range(epochs):
        losses=[]
        for _ in range(max(1,len(points)//16)):
            chosen=rng.choice(classes,min(8,len(classes)),replace=False)
            indices=np.concatenate([rng.choice(np.flatnonzero(targets==c),2,replace=False) for c in chosen])
            losses.append(float(step(points[indices],targets[indices])))
        history.append({'epoch':epoch+1,'contrastive_loss':float(np.mean(losses))})
    return history
