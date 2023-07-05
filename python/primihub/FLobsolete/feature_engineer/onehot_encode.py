import numpy as np
import pandas as pd


class OneHotEncoder():
    def __init__(self):
        self.cats_len = None
        self.cats_idxs = None
        self.categories_ = []
        self.columns = pd.Index([])

    def _check_data(self, data, init=True):
        """
        We recommend using DataFrame as input.
        """
        if isinstance(data, np.ndarray):
            if len(data.shape) == 1:
                return np.reshape(data, (-1, 1))
            elif len(data.shape) > 2:
                raise ValueError("numpy data array shape should be 2-D")
            else:
                return data
        elif isinstance(data, pd.DataFrame):
            if init:
                self.columns = data.columns
            return data.values
        else:
            raise ValueError("data should be numpy data array")

    def _check_idxs(self, idxs):
        if isinstance(idxs, int):
            return [idxs, ]
        elif isinstance(idxs, (tuple, list)):
            idxs = sorted(idxs)
            return idxs
        else:
            raise ValueError("idxs may be int | list | tuple")

    def fit(self, fit_data, idxs1):
        fit_data = self._check_data(fit_data)
        idxs_nd = self._check_idxs(idxs1)

        cats_len = []
        cats_idxs = []
        for idx in idxs_nd:
            tmp_cats = np.unique(fit_data[:, [idx]])
            self.categories_.append(tmp_cats)
            idxs_dict = {k: idx for idx, k in enumerate(tmp_cats)}
            cats_len.append(len(tmp_cats))
            cats_idxs.append(idxs_dict)
        self.cats_len, self.cats_idxs = cats_len, cats_idxs
        return cats_len, cats_idxs

    def onehot_encode(self, trans_data, idxs2):
        for i, idx in enumerate(idxs2):
            tmp_eye = np.eye(self.cats_len[i])
            oh_array = [tmp_eye[self.cats_idxs[i][cat]] for cat in trans_data[:, idx]]
            oh_data = np.array(oh_array) if i == 0 else np.hstack([oh_data, oh_array])
        return oh_data.astype(int)

    def extend_cols(self, drop_idx, cat_idx, insert_idxs):
        postfixs = self.cats_idxs[cat_idx]
        prefix = self.columns[drop_idx]
        ext_cols_name = [
            f"{str(prefix)}_{str(postfix)}" for postfix in postfixs.keys()
        ]
        self.columns = self.columns.drop(prefix)
        for idx, ext_col_name in zip(insert_idxs, ext_cols_name):
            self.columns = self.columns.insert(idx, ext_col_name)

    def transform(self, trans_data, idxs2):
        trans_data = self._check_data(trans_data, init=False)
        idxs_nd = self._check_idxs(idxs2)
        ohed_data = self.onehot_encode(trans_data, idxs2)

        last_idx = 0
        return_data = np.delete(trans_data, idxs_nd, axis=1)
        raw_len = trans_data.shape[1]
        for i, idx in enumerate(idxs_nd):
            # stack onehot_encoded data at the head position
            if idx == 0:
                return_data = np.hstack(
                    [ohed_data[:, list(range(self.cats_len[i]))], return_data[:, :]])
                if self.columns.any():
                    self.extend_cols(idx, i, list(
                        range(idx, idx + self.cats_len[i])))
            elif idx == raw_len-1:
                return_data = np.hstack([return_data[:, :], ohed_data[:, list(
                    range(last_idx, last_idx + self.cats_len[i]))]])
                if self.columns.any():
                    self.extend_cols(-1, i, list(
                        range(idx + last_idx - 1, idx + last_idx + self.cats_len[i] - 1)))
            else:
                tmp_idx = idx if i == 0 else idx + sum(self.cats_len[:i]) - i
                return_data = np.hstack([return_data[:, :tmp_idx], ohed_data[:, list(
                    range(last_idx, last_idx + self.cats_len[i]))], return_data[:, tmp_idx:]])
                if self.columns.any():
                    self.extend_cols(tmp_idx, i, list(
                        range(idx + last_idx, idx + last_idx + self.cats_len[i])))
            last_idx += self.cats_len[i]
        if not self.columns.any():
            return return_data
        assert return_data.shape[1] == len(self.columns)
        return pd.DataFrame(return_data, columns=self.columns)

    def __call__(self, fit_data, trans_data, idxs1, idxs2):
        """
        If you directly call object instance to encode your data, the columns should correspond between fit_data and trans_data.
        """
        self.get_cats(fit_data, idxs1)
        return self.transform(trans_data, idxs2)

    def fit_transform(self, data, idxs):
        return self(data, data, idxs, idxs)

    def get_cats(self, fit_data, idxs1):
        self.fit(fit_data, idxs1)
        return self.categories_


class HorOneHotEncoder(OneHotEncoder):
    def __init__(self):
        super().__init__()

    @staticmethod
    def server_union(*client_cats):
        union_cats_len = []
        union_cats_idxs = []

        for i, cats in enumerate(zip(*client_cats)):
            tmp_union = np.array([])
            for cat in cats:
                tmp_union = np.union1d(tmp_union, cat)
            idxs_dict = {k: idx for idx, k in enumerate(tmp_union)}
            union_cats_len.append(len(tmp_union))
            union_cats_idxs.append(idxs_dict)
        return union_cats_len, union_cats_idxs

    def load_union(self, union_cats_len, union_cats_idxs):
        self.cats_len, self.cats_idxs = union_cats_len, union_cats_idxs
