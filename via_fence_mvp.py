# -*- coding: utf-8 -*-
import math
import pcbnew

# ===== まずは固定パラメータ（あとでUI化） =====
NET_NAME     = "GND"   # viaを所属させるネット名
PITCH_MM     = 1.0     # via間隔
OFFSET_MM    = 0.8     # 中心線からの左右オフセット（片側）
VIA_DIAM_MM  = 0.60    # via外径
VIA_DRILL_MM = 0.30    # ドリル径
DEDUP_GRID_MM = 0.05   # 近接重複をまとめる量子化グリッド

def _msg(text: str):
    """KiCad内でメッセージ表示（wxが無くても落ちないように）"""
    try:
        import wx
        wx.MessageBox(text, "Via Fence MVP")
    except Exception:
        print(text)

def _as_vec2i(pt):
    """VECTOR2Iに揃える（KiCad 7+はSetPositionがVECTOR2I前提）"""
    if isinstance(pt, pcbnew.VECTOR2I):
        return pt
    return pcbnew.VECTOR2I(pt)

class ViaFenceMVP(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Via Fence (MVP)"
        self.category = "RF Tools"
        self.description = "Place 2-row via fence along selected segments (MVP)"
        self.show_toolbar_button = True
        self.icon_file_name = ""  # アイコン欲しければ後で

    def Run(self):
        board = pcbnew.GetBoard()

        # 選択物を取得（KiCad 9 のPython APIで提供） :contentReference[oaicite:8]{index=8}
        sel = pcbnew.GetCurrentSelection()
        if not sel or len(sel) == 0:
            _msg("線分（トラック/グラフィック線など）を選択してから実行してください。")
            return

        net = board.FindNet(NET_NAME)  # net名からNETINFO_ITEMを取れる :contentReference[oaicite:9]{index=9}
        if not net:
            _msg(f"ネット '{NET_NAME}' が見つかりません。NET_NAMEを変更してください。")
            return

        pitch = pcbnew.FromMM(PITCH_MM)
        offset = pcbnew.FromMM(OFFSET_MM)
        via_diam = pcbnew.FromMM(VIA_DIAM_MM)
        via_drill = pcbnew.FromMM(VIA_DRILL_MM)
        dedup_grid = max(1, pcbnew.FromMM(DEDUP_GRID_MM))

        placed_keys = set()
        placed = 0

        def add_via(x_iu: int, y_iu: int):
            nonlocal placed
            # 近すぎる点を重複扱いにして、角で2回打つのを抑制
            k = (int(round(x_iu / dedup_grid)), int(round(y_iu / dedup_grid)))
            if k in placed_keys:
                return
            placed_keys.add(k)

            via = pcbnew.PCB_VIA(board)
            # SetPositionはVECTOR2Iが必要（wxPointだと落ちる/エラーになりやすい） :contentReference[oaicite:10]{index=10}
            via.SetPosition(pcbnew.VECTOR2I(int(x_iu), int(y_iu)))
            via.SetWidth(int(via_diam))
            via.SetDrill(int(via_drill))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)  # 定数はKiCad 9で提供 :contentReference[oaicite:11]{index=11}
            via.SetNet(net)

            board.Add(via)
            placed += 1

        def place_rows_along(p0, p1):
            p0 = _as_vec2i(p0)
            p1 = _as_vec2i(p1)
            dx = p1.x - p0.x
            dy = p1.y - p0.y
            L = math.hypot(dx, dy)
            if L < 1:
                return

            ux = dx / L
            uy = dy / L
            # 左右法線
            nx = -uy
            ny = ux

            nstep = int(L // pitch) + 1
            for i in range(nstep + 1):
                t = min(i * pitch, L)
                cx = p0.x + ux * t
                cy = p0.y + uy * t

                # 左右2列
                add_via(int(round(cx + nx * offset)), int(round(cy + ny * offset)))
                add_via(int(round(cx - nx * offset)), int(round(cy - ny * offset)))

        # ざっくり「Start/Endを持つもの」を線分として扱う（トラックや線分形状）
        segs = 0
        for item in sel:
            # 既存viaを選んでたら無視（viaもtracks系に見えることがあるため）
            if isinstance(item, pcbnew.PCB_VIA):
                continue

            if hasattr(item, "GetStart") and hasattr(item, "GetEnd"):
                try:
                    place_rows_along(item.GetStart(), item.GetEnd())
                    segs += 1
                except Exception as e:
                    _msg(f"一部の要素で処理に失敗しました: {e}")

        pcbnew.Refresh()
        _msg(f"完了: {segs}個の線分から、{placed}個のviaを配置しました。")
