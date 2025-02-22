import tensorflow as tf
import keras.backend as K
from keras.losses import mean_absolute_error


def focal_loss(hm_pred, hm_true):
    pos_mask = tf.cast(tf.equal(hm_true, 1), tf.float32)
    neg_mask = tf.cast(tf.less(hm_true, 1), tf.float32)
    # 离中心点越近, weights 越小
    neg_weights = tf.pow(1 - hm_true, 4)

    pos_loss = -tf.log(tf.clip_by_value(hm_pred, 1e-4, 1. - 1e-4)) * tf.pow(1 - hm_pred, 2) * pos_mask
    neg_loss = -tf.log(tf.clip_by_value(1 - hm_pred, 1e-4, 1. - 1e-4)) * tf.pow(hm_pred, 2) * neg_weights * neg_mask

    num_pos = tf.reduce_sum(pos_mask)
    pos_loss = tf.reduce_sum(pos_loss)
    neg_loss = tf.reduce_sum(neg_loss)

    cls_loss = tf.cond(tf.greater(num_pos, 0), lambda: (pos_loss + neg_loss) / num_pos, lambda: neg_loss)
    return cls_loss


def reg_l1_loss(y_pred, y_true, indices, mask):
    b = tf.shape(y_pred)[0]
    k = tf.shape(indices)[1]
    c = tf.shape(y_pred)[-1]
    y_pred = tf.reshape(y_pred, (b, -1, c))
    indices = tf.cast(indices, tf.int32)
    y_pred = tf.gather(y_pred, indices, batch_dims=1)
    # tile 是为了和 torch 的实现保持一致, (b, k, 2), 这样 mask 增加了 1 倍
    mask = tf.tile(tf.expand_dims(mask, axis=-1), (1, 1, 2))
    total_loss = tf.reduce_sum(tf.abs(y_true * mask - y_pred * mask))
    reg_loss = total_loss / (tf.reduce_sum(mask) + 1e-4)
    return reg_loss


def loss(args):
    hm_pred, wh_pred, reg_pred, hm_true, wh_true, reg_true, reg_mask, indices = args
    hm_loss = focal_loss(hm_pred, hm_true)
    wh_loss = 0.1 * reg_l1_loss(wh_pred, wh_true, indices, reg_mask)
    reg_loss = reg_l1_loss(reg_pred, reg_true, indices, reg_mask)
    total_loss = hm_loss + wh_loss + reg_loss
    return total_loss


if __name__ == '__main__':
    from generators.pascal import PascalVocGenerator
    from models.resnet import centernet
    import numpy as np

    generator = PascalVocGenerator('datasets/VOC0712', 'train',
                                   skip_difficult=True,
                                   shuffle_groups=False,
                                   batch_size=1)

    model, prediction_model, debug_model = centernet(num_classes=20)
    debug_model.load_weights('checkpoints/2019-11-06/pascal_31_1.0370_10.7204.h5',
                             by_name=True,
                             skip_mismatch=True)
    sess = tf.Session()
    for inputs, targets in generator:
        image_input, hm_true, wh_true, reg_true, reg_mask, indices = inputs
        hm_pred, wh_pred, reg_pred = debug_model.predict(image_input)
        np.save('debug/1106/hm_true', hm_true)
        np.save('debug/1106/wh_true', wh_true)
        np.save('debug/1106/reg_true', reg_true)
        np.save('debug/1106/reg_mask', reg_mask)
        np.save('debug/1106/indices', indices)
        np.save('debug/1106/hm_pred', hm_pred)
        np.save('debug/1106/wh_pred', wh_pred)
        np.save('debug/1106/reg_pred', reg_pred)

        print('focal_loss: {}'.format(sess.run(focal_loss(hm_pred, hm_true))))
        print('wh_loss: {}'.format(sess.run(reg_l1_loss(wh_pred, wh_true, indices, reg_mask))))
        print('reg_loss: {}'.format(sess.run(reg_l1_loss(reg_pred, reg_true, indices, reg_mask))))
        print()
