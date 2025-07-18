from typing import Tuple, Optional
import gymnasium as gym
import math

from config import MAX_EXPR_LENGTH
from data.tokens import *
from data.expression import *
from data.tree import ExpressionBuilder
from models.alpha_pool import AlphaPoolBase
from utils import reseed_everything


class AlphaEnvCore(gym.Env):
    pool: AlphaPoolBase
    _tokens: List[Token]
    _builder: ExpressionBuilder
    _print_expr: bool

    def __init__(
        self,
        pool: AlphaPoolBase,
        device: torch.device = torch.device("cuda:0"),
        print_expr: bool = False,
    ):
        super().__init__()

        self.pool = pool
        self._print_expr = print_expr
        self._device = device

        self.eval_cnt = 0

        self.render_mode = None
        self.reset()

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        return_info: bool = False,
        options: Optional[dict] = None
    ) -> Tuple[List[Token], dict]:
        reseed_everything(seed)
        self._tokens = [BEG_TOKEN]
        self._builder = ExpressionBuilder()
        return self._tokens, self._valid_action_types()

    def step(self, action: Token) -> Tuple[List[Token], float, bool, bool, dict]:
        if (
            isinstance(action, SequenceIndicatorToken)
            and action.indicator == SequenceIndicatorType.SEP
        ):  # 如果 action 是 sep 或超出长度
            reward = self._evaluate()  # 计算IC值
            done = True  # 标记此轮循环结束
        elif len(self._tokens) < MAX_EXPR_LENGTH:
            self._tokens.append(action)
            self._builder.add_token(action)
            done = False
            reward = 0.0
        else:
            done = True
            reward = self._evaluate() if self._builder.is_valid() else -1.0

        if math.isnan(reward):
            reward = 0.0

        return self._tokens, reward, done, False, self._valid_action_types()

    def _evaluate(self):
        expr: Expression = self._builder.get_tree()
        if self._print_expr:
            print(expr)  # 给出表达式
        try:
            ret = self.pool.try_new_expr(expr)  # alg1 输出 opt F w
            self.eval_cnt += 1
            return ret
        except OutOfDataRangeError:
            return 0.0

    def _valid_action_types(self) -> dict:
        valid_op_unary = self._builder.validate_op(UnaryOperator)
        valid_op_binary = self._builder.validate_op(BinaryOperator)
        valid_op_rolling = self._builder.validate_op(RollingOperator)
        valid_op_pair_rolling = self._builder.validate_op(PairRollingOperator)

        valid_op = (
            valid_op_unary
            or valid_op_binary
            or valid_op_rolling
            or valid_op_pair_rolling
        )
        valid_feature = self._builder.validate_featured_expr()
        valid_const = self._builder.validate_const()
        valid_dt = self._builder.validate_dt()
        valid_stop = self._builder.is_valid()

        ret = {
            "select": [valid_op, valid_feature, valid_const, valid_dt, valid_stop],
            "op": {
                UnaryOperator: valid_op_unary,
                BinaryOperator: valid_op_binary,
                RollingOperator: valid_op_rolling,
                PairRollingOperator: valid_op_pair_rolling,
            },
        }
        return ret

    def valid_action_types(self) -> dict:
        return self._valid_action_types()

    def render(self, mode="human"):
        pass
