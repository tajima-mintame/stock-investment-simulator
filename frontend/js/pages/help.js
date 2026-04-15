export async function renderHelp(container) {
    container.innerHTML = `
        <h2 style="margin-bottom: 1rem;">使い方</h2>

        <div class="card mb-1">
            <div class="card-title">1. 銘柄を登録する</div>
            <p style="font-size:0.9rem; line-height:1.7; color:var(--text);">
                ダッシュボードの「データ同期」フォームに銘柄コード（例: <code>7203</code>）を入力し、
                期間を指定して「同期」ボタンを押します。<br>
                J-Quants APIから株価データが取得され、チャート表示や分析に使えるようになります。
            </p>
            <div style="margin-top:0.5rem; font-size:0.85rem; color:var(--text-muted);">
                主な銘柄コード: 7203（トヨタ）、9984（ソフトバンクG）、6758（ソニーG）、6861（キーエンス）、8306（三菱UFJ）
            </div>
        </div>

        <div class="card mb-1">
            <div class="card-title">2. チャートを確認する</div>
            <p style="font-size:0.9rem; line-height:1.7; color:var(--text);">
                登録銘柄一覧から銘柄をクリックすると、ローソク足チャートが表示されます。<br>
                テクニカル指標のチェックボックスで以下を表示/非表示できます:
            </p>
            <ul style="font-size:0.85rem; line-height:1.8; color:var(--text-muted); margin:0.5rem 0 0 1.5rem;">
                <li><strong>移動平均線（MA）</strong> — 5日（黄）、25日（青）、75日（紫）の短期〜長期トレンド</li>
                <li><strong>ボリンジャーバンド</strong> — 価格の変動幅を示すバンド（±2σ）</li>
                <li><strong>RSI</strong> — 買われすぎ（70以上）・売られすぎ（30以下）を示す指標</li>
                <li><strong>MACD</strong> — トレンドの転換点を捉えるための指標</li>
            </ul>
        </div>

        <div class="card mb-1">
            <div class="card-title">3. 仮想売買する</div>
            <p style="font-size:0.9rem; line-height:1.7; color:var(--text);">
                銘柄詳細画面の「買い」「売り」ボタン、または「取引」画面から売買を実行します。<br>
                初期資金は <strong>100,000円</strong> です。実際のお金は使いません。
            </p>
            <ul style="font-size:0.85rem; line-height:1.8; color:var(--text-muted); margin:0.5rem 0 0 1.5rem;">
                <li>銘柄コード、数量、価格を入力して「買い」または「売り」を押す</li>
                <li>買い注文: 残高から代金が差し引かれ、保有銘柄に追加される</li>
                <li>売り注文: 保有銘柄から減り、残高に代金が加算される</li>
                <li>損益はFIFO（先入先出法）で計算されます</li>
            </ul>
        </div>

        <div class="card mb-1">
            <div class="card-title">4. ポートフォリオを分析する</div>
            <p style="font-size:0.9rem; line-height:1.7; color:var(--text);">
                「ポートフォリオ」画面で保有銘柄の状況を確認できます。
            </p>
            <ul style="font-size:0.85rem; line-height:1.8; color:var(--text-muted); margin:0.5rem 0 0 1.5rem;">
                <li><strong>保有一覧</strong> — 銘柄ごとの数量・平均取得単価・現在価格・含み損益</li>
                <li><strong>セクター配分</strong> — 業種別の資産配分比率</li>
                <li><strong>相関行列</strong> — 保有銘柄間の値動きの相関（2銘柄以上保有時に表示）</li>
            </ul>
        </div>

        <div class="card mb-1">
            <div class="card-title">5. 銘柄をスクリーニングする</div>
            <p style="font-size:0.9rem; line-height:1.7; color:var(--text);">
                「スクリーニング」画面で登録済み銘柄を条件でフィルタできます。
            </p>
            <ul style="font-size:0.85rem; line-height:1.8; color:var(--text-muted); margin:0.5rem 0 0 1.5rem;">
                <li>セクター、出来高の下限/上限でフィルタ</li>
                <li>出来高・ボラティリティ・変動率でソート</li>
                <li>結果の銘柄をクリックすると詳細画面に遷移</li>
            </ul>
        </div>

        <div class="card mb-1">
            <div class="card-title">6. データを自動収集する</div>
            <p style="font-size:0.9rem; line-height:1.7; color:var(--text);">
                ダッシュボードの「今すぐ収集」ボタンで、ウォッチリストに登録した銘柄のデータを一括更新できます。<br>
                サーバー稼働中は、平日16:00（東証閉場後）に自動収集されます。
            </p>
        </div>

        <div class="card">
            <div class="card-title">用語集</div>
            <table style="font-size:0.85rem;">
                <tr><th style="width:150px;">用語</th><th>説明</th></tr>
                <tr><td>OHLCV</td><td>始値(Open)・高値(High)・安値(Low)・終値(Close)・出来高(Volume)</td></tr>
                <tr><td>移動平均線</td><td>過去N日間の終値の平均値を線で結んだもの</td></tr>
                <tr><td>RSI</td><td>相対力指数。0〜100で買われすぎ・売られすぎを判断（70超: 買われすぎ、30未満: 売られすぎ）</td></tr>
                <tr><td>MACD</td><td>短期EMAと長期EMAの差。シグナル線との交差でトレンド転換を判断</td></tr>
                <tr><td>ボリンジャーバンド</td><td>移動平均線 ± 標準偏差×2。価格がバンド外に出ると反転の可能性</td></tr>
                <tr><td>ボラティリティ</td><td>日次リターンの標準偏差。値が大きいほど価格変動が激しい</td></tr>
                <tr><td>FIFO</td><td>先入先出法。最初に買った株から順に売却したとして損益を計算</td></tr>
                <tr><td>含み損益</td><td>（現在価格 − 平均取得単価）× 保有数量。未確定の損益</td></tr>
                <tr><td>実現損益</td><td>売却時に確定した損益</td></tr>
            </table>
        </div>
    `;
}
