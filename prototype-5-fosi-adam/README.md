This is created in order to rebuild the functionality of prototype-3-fosi-adam experiment such that it will handle everything with a softmax, and not a sigmoid at the end. Leaving space for multi label classification and more.

FOR THE PROBLEM:
* Maybe one solution is to remove the softmax functionality because the grad_fn SoftmaxBackward is causing the problem ?  Calculate the softmax outside of the model!
* The problem was fixed

Problem 2:
* Now there is a problem about the labels, we get different argmax of expected.
       [4, 0],
        [2, 2],
        [1, 4],
        [7, 7],
        [4, 3],
        [1, 1],
        [4, 5],
        [4, 3],
        [3, 3],
        [6, 5],
        [3, 5]])
Labels: tensor([[1, 0],
        [1, 0],
        [0, 1],
        [1, 0],
        [1, 0],
        [1, 0],
        [0, 1],
        [0, 1]])
Epoch: 1, Loss: 3.1237:  60%|█████████████████████████████████                      | 15/25 [00:33<00:22,  2.28s/it]
y_preds in train_val_test() method: tensor([[2, 6],
        [6, 7],
        [0, 4],
        [7, 3],
        [7, 7],
        [0, 4],
        [6, 2],
        [0, 1],
        [5, 5],
        [0, 0],
        [1, 3],
        [2, 6],
        [2, 2],
        [7, 6],
        [3, 4],
        [3, 3],
        [4, 4],
        [7, 3],
        [4, 1],
        [0, 0],
        [3, 0],
        [4, 6],
        [2, 7],
        [1, 4],
        [1, 7],
        [4, 5],
        [1, 1],
        [5, 6],
        [7, 0],
        [7, 2],
        [5, 3],
        [4, 5],
        [6, 1],
        [5, 0],
        [2, 1]])
Labels: tensor([[1, 0],
        [1, 0],
        [0, 1],
        [0, 1],
        [0, 1],
        [0, 1],
        [1, 0],
        [0, 1]])