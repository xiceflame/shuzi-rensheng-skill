#!/bin/bash
# 适配器：把 prompt 写到文件，用户自己粘贴给 ChatGPT/Claude 网页版，再把结果放回 vault。
# 这是「零依赖」路径：系统仍能跑，只是最后一步由人做。
OUT="$HOME/.shuzi-rensheng/manual-$SHUZI_TASK-$(date +%Y%m%d-%H%M).md"
mkdir -p "$(dirname "$OUT")"
{
  echo "# 待人工执行：$SHUZI_TASK"
  echo
  echo "> 把下面整段复制给任意 AI（ChatGPT / Claude 网页版 / 豆包…），"
  echo "> 它需要能读写 $HOME/数字人生/ 。若网页版不能读写文件，就先让它产出内容，你再手动贴进对应页面。"
  echo
  echo '---'
  echo
  echo "$SHUZI_PROMPT"
} > "$OUT"
echo "已写出待办文件：$OUT"
echo "（也打印在下面，可直接复制）"
echo
echo "$SHUZI_PROMPT"
