// This work is licensed under a Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0) https://creativecommons.org/licenses/by-nc-sa/4.0/
// © LuxAlgo
//@version=5

indicator('Market Structure Oscillator + MACD + Stoch RSI (Combo)', 'MSO+MACD+StochRSI', false, format.price, max_lines_count = 500, max_boxes_count = 500, max_labels_count = 500)

//---------------------------------------------------------------------------------------------------------------------
// Settings 
//---------------------------------------------------------------------------------------------------------------------{
display  = display.all - display.status_line

msOsc_Group = 'Market Structure Oscillator'

msOsc_Show  = input(true, "Market Structure Oscillator", group = msOsc_Group)
msWeightK1  = input.float(1, "  Short Term Weight", minval = 0, group = msOsc_Group, step=.1, display = display)
msWeightK2  = input.float(3, "  Intermediate Term Weight", minval = 0, group = msOsc_Group, step=.1, display = display)
msWeightK3  = input.float(2, "  Long Term Weight", minval = 0, group = msOsc_Group, step=.1, display = display)
norm_Smooth = input.int(4, '  Oscillator Smoothing', minval = 1, group = msOsc_Group, display = display)
msBullColor = input.color(#3179f5, '  Gradient Colors: Bullish', inline = 'MS', group = msOsc_Group)
msBearColor = input.color(#ffa726, 'Bearish', inline = 'MS', group = msOsc_Group)
oscSig   = input(false, "Market Structure Oscillator - Crosses (Signals)", group = msOsc_Group)
oBullColor = input.color(#3179f5, '  Signal Colors: Bullish', inline = 'SIG', group = msOsc_Group)
oBearColor = input.color(#ffa726, 'Bearish', inline = 'SIG', group = msOsc_Group)

cyc_Group  = 'Cycle Oscillator'
cycleOpt   = input(true, "Cycle Oscillator - Histogram", group = cyc_Group)
cyc_Smooth = input.int(7, '  Cycle Signal Length', minval = 1, group = cyc_Group, display = display)
cBullColor = input.color(color.new(#90bff9, 25), '  Histogram Colors: Bullish', inline = 'CYC', group = cyc_Group)
cBearColor = input.color(color.new(#ffcc80, 25), 'Bearish', inline = 'CYC', group = cyc_Group)
cycleSig   = input(false, "Cycle Oscillator - Crosses (Signals)", group = cyc_Group)
sBullColor = input.color(color.new(#90bff9, 25), '  Signal Colors: Bullish', inline = 'SIG', group = cyc_Group)
sBearColor = input.color(color.new(#ffcc80, 25), 'Bearish', inline = 'SIG', group = cyc_Group)

genericGroup = 'Market Structures on Chart'
msOnChart1   = input(false, "Short Term Structures", group = genericGroup)
msOnChartK1  = input.string('Dotted', '  Line', options = ['Solid', 'Dashed', 'Dotted'], group = genericGroup, inline = 'K1', display = display)
stMSLblK1T   = input.string('Disabled', 'Labels', options = ['Enabled', 'Disabled'], group = genericGroup, inline = 'K1', display = display), stMSLblK1 = stMSLblK1T == 'Enabled'
cBullColorK1 = input.color(#089981, '  Colors: Bullish', inline = 'K1c', group = genericGroup)
cBearColorK1 = input.color(#f23645, 'Bearish', inline = 'K1c', group = genericGroup)

msOnChart2   = input(false, "Intermediate Term Structures", group = genericGroup)
msOnChartK2  = input.string('Dashed', '  Line', options = ['Solid', 'Dashed', 'Dotted'], group = genericGroup, inline = 'K2', display = display)
stMSLblK2T   = input.string('Disabled', 'Labels', options = ['Enabled', 'Disabled'], group = genericGroup, inline = 'K2', display = display), stMSLblK2 = stMSLblK2T == 'Enabled'
cBullColorK2 = input.color(#089981, '  Colors: Bullish', inline = 'K2c', group = genericGroup)
cBearColorK2 = input.color(#f23645, 'Bearish', inline = 'K2c', group = genericGroup)

msOnChart3   = input(false, "Long Term Structures", group = genericGroup)
msOnChartK3  = input.string('Solid', '  Line', options = ['Solid', 'Dashed', 'Dotted'], group = genericGroup, inline = 'K3', display = display)
stMSLblK3T   = input.string('Enabled', 'Labels', options = ['Enabled', 'Disabled'], group = genericGroup, inline = 'K3', display = display), stMSLblK3 = stMSLblK3T == 'Enabled'
cBullColorK3 = input.color(#089981, '  Colors: Bullish', inline = 'K3c', group = genericGroup)
cBearColorK3 = input.color(#f23645, 'Bearish', inline = 'K3c', group = genericGroup)

msOscCG    = 'Oscillator Components'
msDataK1   = input(false, "Short Term Oscillator", group = msOscCG, inline = 'k1w')
msColorK1  = input(color.new(color.gray, 50), "",  group = msOscCG, inline = 'k1w')

msDataK2   = input(false, "Intermediate Term Oscillator", group = msOscCG, inline = 'k2w')
msColorK2  = input(color.new(color.gray, 50), "", group = msOscCG, inline = 'k2w')

msDataK3   = input(false, "Long Term Oscillator", group = msOscCG, inline = 'k3w')
msColorK3  = input(color.new(color.gray, 50), "", group = msOscCG, inline = 'k3w')

// --- NEW: MACD + StochRSI toggles & params ---
extra_Group = "MACD + StochRSI (Extra)"

macdScaleGroup = "  MACD Scaling"
macdScaleTo100 = input.bool(true, "  Scale MACD to 0–100", group=extra_Group)
macdNormLen    = input.int(200, "  Normalization lookback", minval=20, group=extra_Group)
macdNormSmooth = input.int(3, "  Normalization smoothing", minval=1, group=extra_Group)

showMACD        = input.bool(true,  "Show MACD", group=extra_Group)
showMACDHist    = input.bool(false, "  Show Histogram", group=extra_Group)
sourceInput     = input.source(close, "  Source", group=extra_Group)
fastLenInput    = input.int(12, "  Fast length",   group=extra_Group, minval=1)
slowLenInput    = input.int(26, "  Slow length",   group=extra_Group, minval=1)
sigLenInput     = input.int(9,  "  Signal length", group=extra_Group, minval=1)
oscTypeInput    = input.string("EMA", "  Oscillator MA type", ["EMA", "SMA"], group=extra_Group, display = display.none)
sigTypeInput    = input.string("EMA", "  Signal MA type",     ["EMA", "SMA"], group=extra_Group, display = display.none)


showStochRSI = input.bool(true, "Show Stochastic RSI", group=extra_Group)
rsiLen       = input.int(14, "  RSI Length", group=extra_Group, minval=1)
stochLen     = input.int(14, "  Stoch Length", group=extra_Group, minval=1)
kSmooth      = input.int(3,  "  %K Smoothing", group=extra_Group, minval=1)
dSmooth      = input.int(3,  "  %D Smoothing", group=extra_Group, minval=1)

//---------------------------------------------------------------------------------------------------------------------}
// User Defined Types
//---------------------------------------------------------------------------------------------------------------------{
type BAR
    float   open  = open
    float   high  = high
    float   low   = low
    float   close = close
    int     index = bar_index

type SWINGS
    float   lastPrice
    float   midPrice
    float   prevPrice

    int     lastIndex
    int     midIndex
    int     prevIndex

    bool    isCrossed

type MS
    int type = 0
//---------------------------------------------------------------------------------------------------------------------}
// Variables
//---------------------------------------------------------------------------------------------------------------------{
BAR bar = BAR.new()

var SWINGS stLow  = SWINGS.new()
var SWINGS stHigh = SWINGS.new()
var MS stMS = MS.new()

var SWINGS itLow  = SWINGS.new()
var SWINGS itHigh = SWINGS.new()
var MS itMS = MS.new()

var SWINGS ltLow  = SWINGS.new()
var SWINGS ltHigh = SWINGS.new()
var MS ltMS = MS.new()
//---------------------------------------------------------------------------------------------------------------------}
// Functions / Methods
//---------------------------------------------------------------------------------------------------------------------{
lineStyle(styleInText) =>
    switch styleInText
        'Dotted'    => line.style_dotted
        'Dashed'    => line.style_dashed
        => line.style_solid

queryPatterns(lastPrice, midPrice, prevPrice, isSwingHigh) =>
    if isSwingHigh
        prevPrice < midPrice and midPrice >= lastPrice
    else
        prevPrice > midPrice and midPrice <= lastPrice

method queryPatterns(SWINGS this, isSwingHigh) =>
    if isSwingHigh
        this.prevPrice < this.midPrice and this.midPrice >= this.lastPrice
    else
        this.prevPrice > this.midPrice and this.midPrice <= this.lastPrice

method updatePattern(SWINGS this, price, index) =>
    this.isCrossed := false
    this.prevPrice := this.midPrice, this.midPrice := this.lastPrice, this.lastPrice := price
    this.prevIndex := this.midIndex, this.midIndex := this.lastIndex, this.lastIndex := index

method setType(MS this, value) =>
    this.type := value

normalize(buy, sell, smooth)=>
    var os = 0
    var float max = na
    var float min = na
    os := buy ? 1 : sell ? -1 : os
    
    max := os > os[1] ? bar.close : os < os[1] ? max : math.max(bar.close, max)
    min := os < os[1] ? bar.close : os > os[1] ? min : math.min(bar.close, min)

    ta.sma((bar.close - min)/(max - min), smooth) * 100

shortMarketStructure() => 
    bull = false
    bear = false

    if queryPatterns(high, high[1], high[2], true )
        stHigh.updatePattern(high[1], bar_index[1])
        stHigh.isCrossed := false

    if bar.close > stHigh.lastPrice and not stHigh.isCrossed
        stHigh.isCrossed := true
        bull := true

    if queryPatterns(low , low[1] , low[2] , false) 
        stLow.isCrossed := false
        stLow.updatePattern(low[1], bar_index[1])

    if bar.close < stLow.lastPrice and not stLow.isCrossed
        stLow.isCrossed := true
        bear := true

    normalize(bull, bear, norm_Smooth)

marketStructure(SWINGS hSwingHigh, SWINGS hSwingLow, SWINGS lSwingHigh, SWINGS lSwingLow) => 
    bull = false
    bear = false 

    cSwingHigh = lSwingHigh.queryPatterns(true)

    if cSwingHigh and cSwingHigh != cSwingHigh[1]
        hSwingHigh.updatePattern(lSwingHigh.midPrice, lSwingHigh.midIndex)
        hSwingHigh.isCrossed := false

    if bar.close > hSwingHigh.lastPrice and not hSwingHigh.isCrossed
        hSwingHigh.isCrossed := true
        bull := true

    cSwingLow = lSwingLow.queryPatterns(false)

    if cSwingLow and cSwingLow != cSwingLow[1]
        hSwingLow.updatePattern(lSwingLow.midPrice, lSwingLow.midIndex)
        hSwingLow.isCrossed := false

    if bar.close < hSwingLow.lastPrice and not hSwingLow.isCrossed
        hSwingLow.isCrossed := true
        bear := true

    normalize(bull, bear, norm_Smooth)

collectData() => [shortMarketStructure(), marketStructure(itHigh, itLow, stHigh, stLow), marketStructure(ltHigh, ltLow, itHigh, itLow)]
//---------------------------------------------------------------------------------------------------------------------}
// Calculations - Market Structures on Chart
//---------------------------------------------------------------------------------------------------------------------{
if msOnChart1
    if bar.close > stHigh.lastPrice and not stHigh.isCrossed
        line.new(stHigh.lastIndex, stHigh.lastPrice, bar.index, stHigh.lastPrice, color = cBullColorK1, style = lineStyle(msOnChartK1), width = 1, force_overlay = true)
        if stMSLblK1
            box.new(stHigh.lastIndex, stHigh.lastPrice, bar.index, stHigh.lastPrice, color(na), text = stMS.type < 0 ? 'CHoCH' : 'BoS', text_color = cBullColorK1, text_size = size.tiny, text_halign = text.align_left, text_valign = text.align_bottom, force_overlay = true)
            stMS.setType(1)

    if bar.close < stLow.lastPrice and not stLow.isCrossed
        line.new(stLow.lastIndex, stLow.lastPrice, bar.index, stLow.lastPrice, color = cBearColorK1, style = lineStyle(msOnChartK1), width = 1, force_overlay = true)
        if stMSLblK1
            box.new(stLow.lastIndex, stLow.lastPrice, bar.index, stLow.lastPrice, color(na), text = stMS.type > 0 ? 'CHoCH' : 'BoS', text_color = cBearColorK1, text_size = size.tiny, text_halign = text.align_left, text_valign = text.align_top, force_overlay = true)
            stMS.setType(-1)

if msOnChart2
    if bar.close > itHigh.lastPrice and not itHigh.isCrossed
        line.new(itHigh.lastIndex, itHigh.lastPrice, bar.index, itHigh.lastPrice, color = cBullColorK2, style = lineStyle(msOnChartK2), width = 1, force_overlay = true)
        if stMSLblK2
            box.new(itHigh.lastIndex, itHigh.lastPrice, bar.index, itHigh.lastPrice, color(na), text = itMS.type < 0 ? 'CHoCH' : 'BoS', text_color = cBullColorK2, text_size = size.tiny, text_halign = text.align_left, text_valign = text.align_bottom, force_overlay = true)
            itMS.setType(1)

    if bar.close < itLow.lastPrice and not itLow.isCrossed
        line.new(itLow.lastIndex, itLow.lastPrice, bar.index, itLow.lastPrice, color = cBearColorK2, style = lineStyle(msOnChartK2), width = 1, force_overlay = true)
        if stMSLblK2
            box.new(itLow.lastIndex, itLow.lastPrice, bar.index, itLow.lastPrice, color(na), text = itMS.type > 0 ? 'CHoCH' : 'BoS', text_color = cBearColorK2, text_size = size.tiny, text_halign = text.align_left, text_valign = text.align_top, force_overlay = true)
            itMS.setType(-1)

if msOnChart3
    if bar.close > ltHigh.lastPrice and not ltHigh.isCrossed
        line.new(ltHigh.lastIndex, ltHigh.lastPrice, bar.index, ltHigh.lastPrice, color = cBullColorK3, style = lineStyle(msOnChartK3), width = 1, force_overlay = true)
        if stMSLblK3
            box.new(ltHigh.lastIndex, ltHigh.lastPrice, bar.index, ltHigh.lastPrice, color(na), text = ltMS.type < 0 ? 'CHoCH' : 'BoS', text_color = cBullColorK3, text_size = size.tiny, text_halign = text.align_left, text_valign = text.align_bottom, force_overlay = true)
            ltMS.setType(1)

    if bar.close < ltLow.lastPrice and not ltLow.isCrossed
        line.new(ltLow.lastIndex, ltLow.lastPrice, bar.index, ltLow.lastPrice, color = cBearColorK3, style = lineStyle(msOnChartK3), width = 1, force_overlay = true)
        if stMSLblK3
            box.new(ltLow.lastIndex, ltLow.lastPrice, bar.index, ltLow.lastPrice, color(na), text = ltMS.type > 0 ? 'CHoCH' : 'BoS', text_color = cBearColorK3, text_size = size.tiny, text_halign = text.align_left, text_valign = text.align_top, force_overlay = true)
            ltMS.setType(-1)
//---------------------------------------------------------------------------------------------------------------------}
// Calculations - Oscillator (MSO)
//---------------------------------------------------------------------------------------------------------------------{
oscTop    = plot(msOsc_Show or msDataK1 or msDataK2 or msDataK3 ? 100 : na, 'OSC Top', color(na), display = display.none, editable = false)
upperBand = plot(msOsc_Show or msDataK1 or msDataK2 or msDataK3 ? 85 : na, 'Overbought Level', color(na), display = display.none, editable = false)
midLine   = plot(msOsc_Show or msDataK1 or msDataK2 or msDataK3 ? 50 : na, 'Equilibrium Level', color.new(#787b86, 50), display = display, editable = false)
lowerBand = plot(msOsc_Show or msDataK1 or msDataK2 or msDataK3 ? 15 : na, 'Oversold Level', color(na), display = display.none, editable = false)
oscBtm    = plot(msOsc_Show or msDataK1 or msDataK2 or msDataK3 ? 0 : na, 'OSC Bottom', color(na), display = display.none, editable = false)

fill(oscTop, upperBand, 100, 85, top_color = color.new(msBearColor, 100), bottom_color = color.new(msBearColor, 73), title = "Overbought Fill")
fill(lowerBand, oscBtm, 15, 0, top_color = color.new(msBullColor, 73), bottom_color = color.new(msBullColor, 100), title = "Oversold Fill")

[stValue1, stValue2, stValue3] = collectData()

msOSC  = (msWeightK1 * nz(stValue1, 0) + msWeightK2 * nz(stValue2, 0) + msWeightK3 * nz(stValue3, 0)) / (msWeightK1 * (na(stValue1) ? 0 : 1) + msWeightK2 * (na(stValue2) ? 0 : 1) + msWeightK3 * (na(stValue3) ? 0 : 1))
msPlot = plot(msOsc_Show ? msOSC : na, 'Market Structure Oscillator', color.from_gradient(msOSC, 0, 100, msBearColor, msBullColor), 1, display = display)

if oscSig and ta.change(math.sign(msOSC - 50)) > 0
    label.new(bar.index, bar.low, '⦁', color = color(na), textcolor = oBullColor, style = label.style_label_up, force_overlay = true)
if oscSig and ta.change(math.sign(msOSC - 50)) < 0
    label.new(bar.index, bar.high, '⦁', color = color(na), textcolor = oBearColor, style = label.style_label_down, force_overlay = true)

plot(msDataK1 ? stValue1 : na, 'Short Term Oscillator', msColorK1, 1, display = display)
plot(msDataK2 ? stValue2 : na, 'Intermediate Term Oscillator', msColorK2, 1, display = display)
plot(msDataK3 ? stValue3 : na, 'Long Term Oscillator', msColorK3, 1, display = display)

cycleFast = cycleOpt ? msOSC - ta.ema(msOSC, cyc_Smooth) + 50 : 50
plotcandle(50., 50., 50., cycleFast, 'Cycle Histogram', cycleFast > 50 ? cBullColor : cBearColor, display = display, bordercolor = cycleOpt ? cycleFast > 50 ? cBullColor : cBearColor : color.gray)

if cycleSig and ta.change(math.sign(cycleFast - 50)) > 0
    label.new(bar.index, bar.low, '⦁', color = color(na), textcolor = sBullColor, style = label.style_label_up, force_overlay = true)
if cycleSig and ta.change(math.sign(cycleFast - 50)) < 0
    label.new(bar.index, bar.high, '⦁', color = color(na), textcolor = sBearColor, style = label.style_label_down, force_overlay = true)

fill(msPlot, midLine, 100, cycleOpt ? 60 : 50, top_color = color.new(msBullColor, 0), bottom_color = color.new(msBullColor, 100), title = "Bullish Gradient Fill")
fill(msPlot, midLine, cycleOpt ? 40 : 50, 0, top_color = color.new(msBearColor, 100), bottom_color = color.new(msBearColor, 0), title = "Bearish Gradient Fill")
//---------------------------------------------------------------------------------------------------------------------}

// === Color palette (clean & readable) ===
macdLineColor   = color.rgb(0, 188, 212)     // #00BCD4
macdSignalColor = color.rgb(255, 152, 0)     // #FF9800
macdHistPos     = color.rgb(76, 175, 80)     // #4CAF50
macdHistNeg     = color.rgb(244, 67, 54)     // #F44336

stochKColor     = color.rgb(126, 87, 194)    // #7E57C2
stochDColor     = color.rgb(253, 216, 53)    // #FDD835

bandGray        = color.new(color.gray, 60)
zeroGray        = color.new(color.gray, 60)

//---------------------------------------------------------------------------------------------------------------------
// EXTRA: MACD (TradingView original-style, adapted to v5) + histogram toggle
//---------------------------------------------------------------------------------------------------------------------{
ma(float source, int length, string maType) =>
    maType == "EMA" ? ta.ema(source, length) : ta.sma(source, length)

normalizeTo100(float src, int len) =>
    float lo_ = ta.lowest(src, len)
    float hi_ = ta.highest(src, len)
    hi_ != lo_ ? (src - lo_) / (hi_ - lo_) * 100.0 : 50.0

// Calculate MACD like the original indicator
float maFast = ma(sourceInput, fastLenInput, oscTypeInput)
float maSlow = ma(sourceInput, slowLenInput, oscTypeInput)
float macd   = maFast - maSlow
float signal = ma(macd, sigLenInput, sigTypeInput)
float hist   = macd - signal
float srcForNorm = hist
float norm = normalizeTo100(srcForNorm, macdNormLen)
float normSmoothed = ta.sma(norm, macdNormSmooth)

// Histogram color logic (same idea as original)
color hColor = hist >= 0 ? (hist > hist[1] ? #26a69a : #b2dfdb) : (hist > hist[1] ? #ffcdd2 : #ff5252)

float macdPlotVal   = macdScaleTo100 ? ta.sma(normalizeTo100(macd, macdNormLen), macdNormSmooth) : macd
float signalPlotVal = macdScaleTo100 ? ta.sma(normalizeTo100(signal, macdNormLen), macdNormSmooth) : signal
float histPlotVal   = macdScaleTo100 ? normSmoothed : hist

plot(showMACD ? macdPlotVal : na, "MACD", macdLineColor, linewidth=2)
plot(showMACD ? signalPlotVal : na, "Signal line", macdSignalColor, linewidth=2)
plot(showMACD and showMACDHist ? histPlotVal : na, "Histogram", hColor, style=plot.style_columns)


// Zero line only if MACD is enabled
hline(showMACD ? (macdScaleTo100 ? 50 : 0) : na, "Zero", color.new(#787b86, 40))

// Alert conditions (optional, but nice)
alertcondition(showMACD and hist[1] >= 0 and hist < 0, "Rising to falling", "MACD histogram switched from a rising to falling state")
alertcondition(showMACD and hist[1] <= 0 and hist > 0, "Falling to rising", "MACD histogram switched from a falling to rising state")



//---------------------------------------------------------------------------------------------------------------------}

//---------------------------------------------------------------------------------------------------------------------
// EXTRA: Stochastic RSI (standard 14/14/3/3)
//---------------------------------------------------------------------------------------------------------------------{

rsiValue = ta.rsi(close, rsiLen)
rsiMin   = ta.lowest(rsiValue, stochLen)
rsiMax   = ta.highest(rsiValue, stochLen)
stochRsi = rsiMax != rsiMin ? (rsiValue - rsiMin) / (rsiMax - rsiMin) : 0.0

k = ta.sma(stochRsi * 100.0, kSmooth)
d = ta.sma(k, dSmooth)

plot(showStochRSI ? k : na, title="StochRSI %K", linewidth=2, color=stochKColor)
plot(showStochRSI ? d : na, title="StochRSI %D", linewidth=2, color=stochDColor)
hline(showStochRSI ? 80 : na, "StochRSI Overbought (80)", color=bandGray)
hline(showStochRSI ? 20 : na, "StochRSI Oversold (20)", color=bandGray)
