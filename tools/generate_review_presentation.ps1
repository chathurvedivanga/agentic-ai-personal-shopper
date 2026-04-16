param(
    [string]$OutputPptx = "docs\\AI_Shopping_Partner_Project_Review_Deck.pptx",
    [string]$OutputPdf = "docs\\AI_Shopping_Partner_Project_Review_Deck.pdf"
)

$ErrorActionPreference = "Stop"

function New-OleColor {
    param(
        [int]$R,
        [int]$G,
        [int]$B
    )

    return [int]($R + (256 * $G) + (65536 * $B))
}

$Colors = @{
    Background = New-OleColor 11 13 18
    Panel      = New-OleColor 22 26 34
    PanelAlt   = New-OleColor 18 21 28
    Border     = New-OleColor 73 81 96
    Text       = New-OleColor 244 246 248
    Muted      = New-OleColor 176 182 191
    Accent     = New-OleColor 210 180 96
    AccentSoft = New-OleColor 137 146 165
}

$Fonts = @{
    Title = "Aptos Display"
    Body  = "Aptos"
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputPptxPath = Join-Path $ProjectRoot $OutputPptx
$OutputPdfPath = Join-Path $ProjectRoot $OutputPdf

$Screenshots = @{
    Home        = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120536.png"
    PromptDraft = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120552.png"
    LiveSearch  = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120602.png"
    Sources     = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120703.png"
    Output1     = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 121207.png"
    Output2     = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 121235.png"
    Output3     = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 121253.png"
}

function Set-CommonTextStyle {
    param(
        $TextRange,
        [string]$FontName,
        [double]$FontSize,
        [int]$Color,
        [bool]$Bold = $false
    )

    $TextRange.Font.Name = $FontName
    $TextRange.Font.Size = $FontSize
    $TextRange.Font.Color.RGB = $Color
    $TextRange.Font.Bold = $(if ($Bold) { -1 } else { 0 })
}

function Add-TextBox {
    param(
        $Slide,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string]$Text,
        [double]$FontSize = 18,
        [int]$Color = $Colors.Text,
        [bool]$Bold = $false,
        [string]$FontName = $Fonts.Body
    )

    $shape = $Slide.Shapes.AddTextbox(1, $Left, $Top, $Width, $Height)
    $shape.TextFrame.TextRange.Text = $Text
    $shape.TextFrame.WordWrap = -1
    $shape.Fill.Transparency = 1
    $shape.Line.Visible = 0
    Set-CommonTextStyle -TextRange $shape.TextFrame.TextRange -FontName $FontName -FontSize $FontSize -Color $Color -Bold $Bold
    return $shape
}

function Add-BulletList {
    param(
        $Slide,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string[]]$Items,
        [double]$FontSize = 18,
        [int]$Color = $Colors.Text
    )

    $text = ($Items | ForEach-Object { "• $_" }) -join "`r"
    $shape = Add-TextBox -Slide $Slide -Left $Left -Top $Top -Width $Width -Height $Height -Text $text -FontSize $FontSize -Color $Color -Bold $false
    foreach ($paragraph in $shape.TextFrame.TextRange.Paragraphs()) {
        $paragraph.ParagraphFormat.SpaceAfter = 6
        $paragraph.ParagraphFormat.SpaceBefore = 0
    }
    return $shape
}

function Add-BulletList {
    param(
        $Slide,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string[]]$Items,
        [double]$FontSize = 18,
        [int]$Color = $Colors.Text
    )

    $text = $Items -join "`r"
    $shape = Add-TextBox -Slide $Slide -Left $Left -Top $Top -Width $Width -Height $Height -Text $text -FontSize $FontSize -Color $Color -Bold $false
    foreach ($paragraph in $shape.TextFrame.TextRange.Paragraphs()) {
        $paragraph.ParagraphFormat.Bullet.Visible = -1
        $paragraph.ParagraphFormat.Bullet.Character = 8226
        $paragraph.ParagraphFormat.SpaceAfter = 6
        $paragraph.ParagraphFormat.SpaceBefore = 0
    }
    return $shape
}

function Add-Panel {
    param(
        $Slide,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [int]$FillColor = $Colors.Panel
    )

    $shape = $Slide.Shapes.AddShape(1, $Left, $Top, $Width, $Height)
    $shape.Fill.Solid()
    $shape.Fill.ForeColor.RGB = $FillColor
    $shape.Line.ForeColor.RGB = $Colors.Border
    $shape.Line.Weight = 1
    return $shape
}

function Add-SlideBase {
    param(
        $Presentation,
        [string]$Title,
        [string]$Section = ""
    )

    $slide = $Presentation.Slides.Add($Presentation.Slides.Count + 1, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $Colors.Background

    $line = $slide.Shapes.AddLine(36, 54, $Presentation.PageSetup.SlideWidth - 36, 54)
    $line.Line.ForeColor.RGB = $Colors.Border
    $line.Line.Weight = 1.15

    $titleBox = $slide.Shapes.AddTextbox(1, 36, 14, 610, 34)
    $titleBox.TextFrame.TextRange.Text = $Title
    $titleBox.TextFrame.WordWrap = -1
    $titleBox.Fill.Transparency = 1
    $titleBox.Line.Visible = 0
    Set-CommonTextStyle -TextRange $titleBox.TextFrame.TextRange -FontName $Fonts.Title -FontSize 24 -Color $Colors.Text -Bold $true

    if ($Section) {
        $sectionBox = $slide.Shapes.AddTextbox(1, $Presentation.PageSetup.SlideWidth - 260, 18, 220, 18)
        $sectionBox.TextFrame.TextRange.Text = $Section.ToUpper()
        $sectionBox.Fill.Transparency = 1
        $sectionBox.Line.Visible = 0
        Set-CommonTextStyle -TextRange $sectionBox.TextFrame.TextRange -FontName $Fonts.Body -FontSize 10 -Color $Colors.Accent -Bold $false
        $sectionBox.TextFrame.TextRange.ParagraphFormat.Alignment = 3
    }

    $footer = $slide.Shapes.AddTextbox(1, $Presentation.PageSetup.SlideWidth - 62, $Presentation.PageSetup.SlideHeight - 26, 26, 14)
    $footer.TextFrame.TextRange.Text = [string]$slide.SlideIndex
    $footer.Fill.Transparency = 1
    $footer.Line.Visible = 0
    Set-CommonTextStyle -TextRange $footer.TextFrame.TextRange -FontName $Fonts.Body -FontSize 9 -Color $Colors.AccentSoft -Bold $false
    $footer.TextFrame.TextRange.ParagraphFormat.Alignment = 3

    return $slide
}

function Add-ImageFit {
    param(
        $Slide,
        [string]$Path,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string]$Caption = ""
    )

    $frame = Add-Panel -Slide $Slide -Left $Left -Top $Top -Width $Width -Height $Height -FillColor $Colors.PanelAlt
    $frame.Fill.Transparency = 0.1

    $pic = $Slide.Shapes.AddPicture($Path, 0, -1, 0, 0, -1, -1)
    $pic.LockAspectRatio = -1
    $scale = [Math]::Min($Width / $pic.Width, $Height / $pic.Height)
    $pic.Width = $pic.Width * $scale
    $pic.Height = $pic.Height * $scale
    $pic.Left = $Left + (($Width - $pic.Width) / 2)
    $pic.Top = $Top + (($Height - $pic.Height) / 2)

    if ($Caption) {
        $captionBox = Add-TextBox -Slide $Slide -Left $Left -Top ($Top + $Height + 6) -Width $Width -Height 18 -Text $Caption -FontSize 10 -Color $Colors.Muted -Bold $false
        $captionBox.TextFrame.TextRange.ParagraphFormat.Alignment = 3
    }

    return $pic
}

function Set-TableCell {
    param(
        $Cell,
        [string]$Text,
        [double]$FontSize,
        [int]$FillColor,
        [int]$TextColor,
        [bool]$Bold = $false
    )

    $Cell.Shape.Fill.Solid()
    $Cell.Shape.Fill.ForeColor.RGB = $FillColor
    $Cell.Shape.TextFrame.MarginLeft = 6
    $Cell.Shape.TextFrame.MarginRight = 6
    $Cell.Shape.TextFrame.MarginTop = 4
    $Cell.Shape.TextFrame.MarginBottom = 4
    $Cell.Shape.TextFrame.TextRange.Text = $Text
    Set-CommonTextStyle -TextRange $Cell.Shape.TextFrame.TextRange -FontName $Fonts.Body -FontSize $FontSize -Color $TextColor -Bold $Bold
}

function Add-Table {
    param(
        $Slide,
        [double]$Left,
        [double]$Top,
        [double]$Width,
        [double]$Height,
        [string[]]$Headers,
        [object[][]]$Rows,
        [double]$HeaderFontSize = 12,
        [double]$BodyFontSize = 11
    )

    $shape = $Slide.Shapes.AddTable($Rows.Count + 1, $Headers.Count, $Left, $Top, $Width, $Height)
    $table = $shape.Table

    for ($c = 1; $c -le $Headers.Count; $c++) {
        Set-TableCell -Cell $table.Cell(1, $c) -Text $Headers[$c - 1] -FontSize $HeaderFontSize -FillColor $Colors.Panel -TextColor $Colors.Accent -Bold $true
    }

    for ($r = 0; $r -lt $Rows.Count; $r++) {
        for ($c = 0; $c -lt $Headers.Count; $c++) {
            $rowColor = if (($r % 2) -eq 0) { $Colors.PanelAlt } else { $Colors.Panel }
            Set-TableCell -Cell $table.Cell($r + 2, $c + 1) -Text ([string]$Rows[$r][$c]) -FontSize $BodyFontSize -FillColor $rowColor -TextColor $Colors.Text -Bold $false
        }
    }

    return $shape
}

function Add-TwoColumnBulletSlide {
    param(
        $Presentation,
        [string]$Title,
        [string]$Section,
        [string]$LeftHeading,
        [string[]]$LeftItems,
        [string]$RightHeading,
        [string[]]$RightItems
    )

    $slide = Add-SlideBase -Presentation $Presentation -Title $Title -Section $Section
    Add-TextBox -Slide $slide -Left 44 -Top 78 -Width 400 -Height 20 -Text $LeftHeading -FontSize 13 -Color $Colors.Accent -Bold $true | Out-Null
    Add-Panel -Slide $slide -Left 36 -Top 102 -Width 410 -Height 360 -FillColor $Colors.PanelAlt | Out-Null
    Add-BulletList -Slide $slide -Left 54 -Top 122 -Width 372 -Height 320 -Items $LeftItems -FontSize 16 -Color $Colors.Text | Out-Null

    Add-TextBox -Slide $slide -Left 500 -Top 78 -Width 400 -Height 20 -Text $RightHeading -FontSize 13 -Color $Colors.Accent -Bold $true | Out-Null
    Add-Panel -Slide $slide -Left 492 -Top 102 -Width 432 -Height 360 -FillColor $Colors.PanelAlt | Out-Null
    Add-BulletList -Slide $slide -Left 510 -Top 122 -Width 394 -Height 320 -Items $RightItems -FontSize 16 -Color $Colors.Text | Out-Null

    return $slide
}

function Add-CoverSlide {
    param($Presentation)

    $slide = $Presentation.Slides.Add($Presentation.Slides.Count + 1, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $Colors.Background

    $accentLine = $slide.Shapes.AddLine(36, 56, 430, 56)
    $accentLine.Line.ForeColor.RGB = $Colors.Accent
    $accentLine.Line.Weight = 2

    Add-TextBox -Slide $slide -Left 36 -Top 24 -Width 330 -Height 18 -Text "PROJECT REVIEW DECK" -FontSize 12 -Color $Colors.Accent -Bold $true | Out-Null
    Add-TextBox -Slide $slide -Left 36 -Top 72 -Width 410 -Height 88 -Text "Agentic AI`rPersonal Shopper" -FontSize 28 -Color $Colors.Text -Bold $true -FontName $Fonts.Title | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 182 -Width 390 -Height 170 -Items @(
        "Full-stack AI shopping assistant for evidence-grounded product decisions",
        "Built with React, Flask, Gemini, YouTube transcript research, SSE, and Postgres",
        "Review scope: vision, architecture, engineering journey, deployment, and outcomes"
    ) -FontSize 16 -Color $Colors.Text | Out-Null

    $metaHeaders = @("Item", "Details")
    $metaRows = @(
        @("Names", "V Rama Chandra Chathurvedi, Aravind Prasad R"),
        @("Reg. No.", "25MCS0067, 25MCS0060"),
        @("Guide", "Dr. Baiju B V"),
        @("Project", "AI Shopping Partner")
    )
    Add-Table -Slide $slide -Left 36 -Top 360 -Width 390 -Height 140 -Headers $metaHeaders -Rows $metaRows -HeaderFontSize 11 -BodyFontSize 10 | Out-Null
    Add-ImageFit -Slide $slide -Path $Screenshots.Home -Left 470 -Top 42 -Width 450 -Height 430 -Caption "Final landing experience of the deployed web application" | Out-Null
}

if (Test-Path $OutputPptxPath) {
    Remove-Item $OutputPptxPath -Force
}

if (Test-Path $OutputPdfPath) {
    Remove-Item $OutputPdfPath -Force
}

$powerPoint = $null
$presentation = $null

try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = -1
    $presentation = $powerPoint.Presentations.Add()
    $presentation.PageSetup.SlideWidth = 960
    $presentation.PageSetup.SlideHeight = 540

    Add-CoverSlide -Presentation $presentation

    $slide = Add-SlideBase -Presentation $presentation -Title "Executive Summary and Core Ideologies" -Section "Vision"
    $headers = @("Core ideology", "How it was implemented", "Review value")
    $rows = @(
        @("Evidence-grounded shopping", "Recommendations synthesized from YouTube review transcripts and explicit source links", "Moves output away from generic chatbot advice"),
        @("Conversational continuity", "Follow-up questions, saved sessions, auto-titles, rename/delete, sidebar revisit flow", "Lets users continue buying decisions over time"),
        @("Latency-conscious engineering", "ThreadPoolExecutor, SSE streaming, hybrid tool routing, lighter transcript payloads, caching", "Improves both real and perceived responsiveness"),
        @("Privacy-first persistence", "Anonymous browser-scoped ownership for each session", "Prevents chat leakage on a public website"),
        @("Deployment realism", "GitHub source control, Render Blueprint, Postgres, env wiring, health checks", "Makes the project review-ready beyond localhost")
    )
    Add-Table -Slide $slide -Left 36 -Top 88 -Width 888 -Height 360 -Headers $headers -Rows $rows -HeaderFontSize 12 -BodyFontSize 11 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 462 -Width 888 -Height 48 -Items @(
        "Overall design target: a practical AI shopping product, not a toy demo."
    ) -FontSize 13 -Color $Colors.AccentSoft | Out-Null

    Add-TwoColumnBulletSlide -Presentation $presentation -Title "Problem Statement and Project Goals" -Section "Why this project" `
        -LeftHeading "Problem being solved" `
        -LeftItems @(
            "Online product research is fragmented across videos, specs, comments, and opinions.",
            "Buyers need verdicts and comparisons, not just a list of links.",
            "Typical chatbots often lack cited evidence and strong session continuity.",
            "Public deployment introduces privacy and persistence challenges."
        ) `
        -RightHeading "Project goals" `
        -RightItems @(
            "Accept natural-language shopping requests and follow-up questions.",
            "Search YouTube reviews only when fresh evidence is required.",
            "Extract transcripts automatically and synthesize a shopping verdict.",
            "Stream responses live and save research for later reuse.",
            "Deploy publicly with a professional UI and production-style persistence."
        ) | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Development Timeline: From MVP to Public Deployment" -Section "Journey"
    $headers = @("Phase", "What was built", "Outcome")
    $rows = @(
        @("1. Foundation", "React/Vite frontend shell + modular Flask backend (app.py, agent.py, scraper.py)", "Stable starting architecture"),
        @("2. Retrieval + AI", "YouTube search, transcript extraction, Gemini synthesis, SSE streaming", "End-to-end chat research flow"),
        @("3. Product UX", "Dark interface, prompt composer, source chips, better output formatting", "Professional and review-friendly UI"),
        @("4. Session features", "Saved chats, smart title generation, rename/delete, sidebar navigation", "Conversation continuity"),
        @("5. Hardening", "Privacy isolation, latency fixes, model fallback, Render/Postgres deployment", "Publicly usable system")
    )
    Add-Table -Slide $slide -Left 36 -Top 98 -Width 888 -Height 320 -Headers $headers -Rows $rows -HeaderFontSize 12 -BodyFontSize 12 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 434 -Width 888 -Height 70 -Items @(
        "The project evolved from a functional prototype into a production-style full-stack application.",
        "Each iteration addressed a real engineering limitation: reliability, speed, privacy, or UX clarity."
    ) -FontSize 15 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Initial Scope vs Final Delivered System" -Section "Requirements"
    $headers = @("Area", "Initial requirement", "Final implementation", "Status")
    $rows = @(
        @("Backend structure", "app.py, agent.py, scraper.py", "Added storage.py, session CRUD routes, privacy ownership, deployment-ready configuration", "Delivered"),
        @("Intent routing", "Fast decision on whether fresh YouTube research is needed", "Hybrid fast-path research + Gemini tool decision for ambiguous turns", "Delivered"),
        @("Parallel retrieval", "Fetch top video transcripts in parallel", "Multi-variant search + dedupe + ThreadPoolExecutor transcript extraction", "Delivered"),
        @("Streaming", "Gemini response streamed to UI", "SSE with session, status, sources, chunk, done, and error events", "Delivered"),
        @("Chat UI", "Modern conversational interface", "Dark minimal interface with collapsible sidebar and keyboard-first composer", "Delivered"),
        @("History", "Maintain conversation context", "Saved chats, smart titles, rename/delete, DB persistence, browser privacy", "Delivered")
    )
    Add-Table -Slide $slide -Left 24 -Top 86 -Width 912 -Height 376 -Headers $headers -Rows $rows -HeaderFontSize 11 -BodyFontSize 10 | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Technology Stack and Platform Choices" -Section "Stack"
    $headers = @("Layer", "Technology", "Purpose", "Why this choice")
    $rows = @(
        @("Frontend", "React + Vite + Tailwind CSS + react-markdown", "Interactive chat UI and fast development", "Component-based, responsive, lightweight, markdown-friendly"),
        @("Backend API", "Python Flask + Gunicorn", "REST API, SSE streaming, routing", "Simple, modular, and suitable for Render web services"),
        @("AI layer", "Google Gemini Flash family", "Product verdicts, comparisons, titles", "Fast enough for conversational synthesis"),
        @("Retrieval", "youtube-search-python + youtube-transcript-api", "Review discovery and evidence extraction", "No official YouTube Data API keys required"),
        @("Persistence", "SQLite locally, Postgres on Render", "Session and message storage", "Easy local setup + durable production deployment"),
        @("Deployment", "GitHub + Render Blueprint", "Public hosting and infra wiring", "Straightforward for Flask, SSE, and Postgres")
    )
    Add-Table -Slide $slide -Left 24 -Top 86 -Width 912 -Height 388 -Headers $headers -Rows $rows -HeaderFontSize 11 -BodyFontSize 10 | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "System Architecture and End-to-End Flow" -Section "Architecture"
    $headers = @("Stage", "Responsible layer", "Output / behavior")
    $rows = @(
        @("1. Prompt entry", "React frontend", "Captures query, updates local state, opens/uses active session"),
        @("2. Chat request", "Flask POST /api/chat", "Creates or resumes a session and starts streaming events"),
        @("3. Routing", "agent.py", "Decides follow-up vs fresh YouTube research"),
        @("4. Evidence retrieval", "scraper.py", "Search variants + parallel transcript extraction + source list"),
        @("5. Synthesis", "Gemini", "Generates verdict, compare blocks, watch-outs, and INR pricing cues"),
        @("6. Streaming", "SSE", "Delivers status, source chips, and text chunks in real time"),
        @("7. Persistence", "storage.py", "Stores messages, sessions, titles, and owner-scoped visibility"),
        @("8. Revisit", "Sidebar + session API", "Lets user reopen, rename, or delete research threads")
    )
    Add-Table -Slide $slide -Left 36 -Top 92 -Width 888 -Height 334 -Headers $headers -Rows $rows -HeaderFontSize 12 -BodyFontSize 11 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 440 -Width 888 -Height 58 -Items @(
        "SSE event contract used by the UI: session, status, sources, chunk, done, and error.",
        "Architecture intentionally separates routing, retrieval, synthesis, storage, and presentation concerns."
    ) -FontSize 14 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Backend Module Design" -Section "Implementation"
    $headers = @("Module", "Primary responsibilities", "Notable implementation details")
    $rows = @(
        @("app.py", "Flask setup, CORS, routes, SSE streaming, session endpoints", "Owns POST /api/chat, health checks, title scheduling, and cookie identity"),
        @("agent.py", "Gemini orchestration and shopping reasoning", "Hybrid routing, tool wrapper, model fallback, response policy, title generation"),
        @("scraper.py", "YouTube search and transcript extraction", "India-focused query shaping, transcript fallback logic, dedupe, caching support"),
        @("storage.py", "DB schema and CRUD", "SQLite local fallback, Postgres production support, owner-scoped session filtering")
    )
    Add-Table -Slide $slide -Left 36 -Top 100 -Width 888 -Height 240 -Headers $headers -Rows $rows -HeaderFontSize 12 -BodyFontSize 11 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 356 -Width 888 -Height 120 -Items @(
        "The modular backend kept routing, research, model logic, and persistence independently maintainable.",
        "This structure also made it easier to debug individual issues such as quota failures, transcript failures, and chat leakage."
    ) -FontSize 15 -Color $Colors.Text | Out-Null

    Add-TwoColumnBulletSlide -Presentation $presentation -Title "YouTube Retrieval Engine and Gemini Intelligence" -Section "AI orchestration" `
        -LeftHeading "YouTube evidence pipeline" `
        -LeftItems @(
            "Derived search variants from the user query with India- and review-oriented bias.",
            "Searched multiple candidate videos and removed duplicates.",
            "Fetched transcripts in parallel with ThreadPoolExecutor for lower latency.",
            "Skipped videos that raised TranscriptsDisabled or NoTranscriptFound.",
            "Used transcript fallbacks, trimming, and caching before passing evidence to Gemini."
        ) `
        -RightHeading "Gemini orchestration strategy" `
        -RightItems @(
            "Wrapped YouTube research as a native tool: fetch_youtube_reviews(product_name).",
            "Used a hybrid router: fast-path for obvious new research, model decision for ambiguous or follow-up turns.",
            "Streamed final responses through SSE for a live typing effect.",
            "Added stronger prompts for specific models, INR budgets, comparisons, and watch-outs.",
            "Introduced model fallback and quota-aware behavior for public deployment."
        ) | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Frontend UX and Interaction Design" -Section "User experience"
    $headers = @("UX objective", "Final implementation")
    $rows = @(
        @("Minimal visual noise", "Dark, low-glare interface with centered landing page and restrained accent colors"),
        @("Fast first interaction", "Suggestion chips, large composer, keyboard-first prompt flow"),
        @("Streaming clarity", "Live status labels, source chips, incremental answer rendering"),
        @("Navigation", "Collapsible sidebar, home click behavior, draft/new chat flow"),
        @("Session control", "Rename, delete, revisit, and single smart auto-title generation"),
        @("Responsiveness", "Desktop sidebar plus mobile-friendly drawer behavior")
    )
    Add-Table -Slide $slide -Left 72 -Top 108 -Width 816 -Height 274 -Headers $headers -Rows $rows -HeaderFontSize 12 -BodyFontSize 12 | Out-Null
    Add-BulletList -Slide $slide -Left 72 -Top 404 -Width 816 -Height 86 -Items @(
        "The UI deliberately moved away from cluttered tables and duplicated controls.",
        "The final design aligns more closely with the interaction patterns of ChatGPT, Gemini, Claude, and Copilot."
    ) -FontSize 15 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "UI Walkthrough: Landing State and Prompt Entry" -Section "Screens"
    Add-ImageFit -Slide $slide -Path $Screenshots.Home -Left 36 -Top 88 -Width 425 -Height 330 -Caption "Home view before a prompt is sent" | Out-Null
    Add-ImageFit -Slide $slide -Path $Screenshots.PromptDraft -Left 499 -Top 88 -Width 425 -Height 330 -Caption "Prompt drafted for a specific Indian-market shopping query" | Out-Null
    Add-BulletList -Slide $slide -Left 52 -Top 435 -Width 860 -Height 70 -Items @(
        "Clean landing page with one clear call to action: ask a shopping question.",
        "Prompt suggestions accelerate first use and demonstrate supported query styles.",
        "Composer supports Enter-to-send and Shift+Enter for multiline prompts."
    ) -FontSize 14 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "UI Walkthrough: Live Research and Streaming States" -Section "Screens"
    Add-ImageFit -Slide $slide -Path $Screenshots.LiveSearch -Left 80 -Top 82 -Width 800 -Height 320 -Caption "Thread begins with the user message and immediately surfaces live research status" | Out-Null
    $headers = @("State", "Meaning")
    $rows = @(
        @("Searching YouTube", "Retrieval is running and transcript evidence is being collected"),
        @("Live", "Assistant stream is active and the response channel is open"),
        @("Working", "Composer is locked to prevent conflicting requests during an active run"),
        @("Stop", "User can interrupt the active generation")
    )
    Add-Table -Slide $slide -Left 154 -Top 424 -Width 652 -Height 82 -Headers $headers -Rows $rows -HeaderFontSize 11 -BodyFontSize 10 | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "UI Walkthrough: Source Transparency During Generation" -Section "Screens"
    Add-ImageFit -Slide $slide -Path $Screenshots.Sources -Left 54 -Top 82 -Width 852 -Height 344 -Caption "Source links are surfaced while the verdict is still being drafted" | Out-Null
    Add-BulletList -Slide $slide -Left 54 -Top 438 -Width 852 -Height 62 -Items @(
        "Multiple review channels contribute evidence instead of relying on a single video.",
        "Users can see exactly which review videos informed the answer before the response completes.",
        "This improves trust, explainability, and review auditability."
    ) -FontSize 14 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Recommendation Output: Verdict and Quick Compare" -Section "Screens"
    Add-ImageFit -Slide $slide -Path $Screenshots.Output1 -Left 66 -Top 78 -Width 828 -Height 332 -Caption "Final answer format emphasizes verdict, quick compare blocks, watch-outs, and pricing" | Out-Null
    Add-BulletList -Slide $slide -Left 66 -Top 426 -Width 828 -Height 82 -Items @(
        "The output moved away from clumsy markdown tables toward compact compare blocks.",
        "Each recommendation includes best-for guidance, gaming/performance notes, battery, watch-outs, and approximate INR pricing.",
        "When transcript access is limited, the assistant degrades gracefully instead of failing outright."
    ) -FontSize 14 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Recommendation Output: Product-Level Specificity" -Section "Screens"
    Add-ImageFit -Slide $slide -Path $Screenshots.Output2 -Left 66 -Top 78 -Width 828 -Height 332 -Caption "Recommendations are presented as concrete product options rather than brand-only advice" | Out-Null
    Add-BulletList -Slide $slide -Left 66 -Top 426 -Width 828 -Height 82 -Items @(
        "The response policy was strengthened to prefer exact models and budget-relevant shortlists.",
        "Ambiguous categories can trigger clarifications instead of generic recommendations.",
        "India-focused pricing improves practical decision support for the target audience."
    ) -FontSize 14 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Recommendation Output: Attached Evidence Links" -Section "Screens"
    Add-ImageFit -Slide $slide -Path $Screenshots.Output3 -Left 66 -Top 78 -Width 828 -Height 332 -Caption "Source chips remain attached to the recommendation output for quick verification" | Out-Null
    Add-BulletList -Slide $slide -Left 66 -Top 426 -Width 828 -Height 82 -Items @(
        "Final answers keep source visibility close to the recommendation itself.",
        "This supports follow-up questions such as battery, thermals, value, or camera trade-offs.",
        "The UI is designed to feel conversational while still preserving evidence grounding."
    ) -FontSize 14 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Sessions, Privacy, and Persistence" -Section "State management"
    $headers = @("Capability", "Final behavior", "Engineering mechanism")
    $rows = @(
        @("Saved sessions", "Reopen earlier chats from the sidebar", "Session and message tables in DB"),
        @("Rename / delete", "Users control chat titles and cleanup", "PATCH/DELETE session endpoints + sidebar actions"),
        @("Single smart auto-title", "One refined title appears after the first answer", "Background title generation after assistant response"),
        @("Browser-private chats", "One visitor cannot see another visitor's conversations", "Anonymous cookie + owner_id session filtering"),
        @("Local and production storage", "SQLite locally, Postgres on Render", "DB_PATH fallback locally, DATABASE_URL in production")
    )
    Add-Table -Slide $slide -Left 36 -Top 94 -Width 888 -Height 280 -Headers $headers -Rows $rows -HeaderFontSize 12 -BodyFontSize 11 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 390 -Width 888 -Height 110 -Items @(
        "A critical late-stage fix was preventing public chat leakage once the site was deployed on a shared URL.",
        "Authentication was intentionally avoided to keep the product lightweight, so privacy was implemented per browser session instead."
    ) -FontSize 15 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Deployment Architecture and Production Setup" -Section "Deployment"
    $headers = @("Deployment layer", "What was done", "Outcome")
    $rows = @(
        @("Source control", "Initialized Git repository, created GitHub repo, documented setup in README", "Reproducible project history"),
        @("Backend hosting", "Deployed Flask API to Render Web Service with Gunicorn", "Public SSE-capable API"),
        @("Frontend hosting", "Deployed Vite build to Render Static Site", "Public client URL"),
        @("Database", "Provisioned Render Postgres and injected DATABASE_URL", "Durable session persistence in production"),
        @("Configuration", "Wired GEMINI_API_KEY, CORS_ORIGIN, VITE_API_BASE_URL, health checks", "Connected services and prevented CORS issues"),
        @("Operational fit", "Chose Render over Vercel for Flask + SSE + long-lived backend patterns", "Simpler deployment model for this architecture")
    )
    Add-Table -Slide $slide -Left 24 -Top 90 -Width 912 -Height 320 -Headers $headers -Rows $rows -HeaderFontSize 11 -BodyFontSize 10 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 426 -Width 888 -Height 70 -Items @(
        "Production persistence was upgraded from SQLite to Postgres because free service filesystems are not durable enough for shared deployment.",
        "A Render Blueprint (render.yaml) keeps frontend, backend, and database wiring aligned."
    ) -FontSize 14 -Color $Colors.Text | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Major Technical Issues and Their Resolutions" -Section "Lessons learned"
    $headers = @("Issue", "Observed problem", "Resolution")
    $rows = @(
        @("PowerShell execution policy", "Blocked venv activation and direct npm usage", "Used .venv\\Scripts\\python and npm.cmd instead of changing global policy"),
        @("Python dependency mismatch", "youtube-transcript-api 0.6.3 failed on Python 3.14", "Upgraded to a compatible version"),
        @("YouTube search breakage", "youtube-search-python conflicted with newer httpx", "Pinned a compatible httpx release"),
        @("Gemini model / config errors", "Unavailable model aliases and invalid function calling config", "Updated model defaults, added fallback logic, corrected tool config"),
        @("Quota exhaustion", "Public traffic exceeded free-tier request limits", "Added model fallback, better usage patterns, and quota-aware messaging")
    )
    Add-Table -Slide $slide -Left 24 -Top 92 -Width 912 -Height 346 -Headers $headers -Rows $rows -HeaderFontSize 11 -BodyFontSize 10 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 452 -Width 888 -Height 48 -Items @(
        "These issues were part of turning the app from a local prototype into a public deployment."
    ) -FontSize 14 -Color $Colors.AccentSoft | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Major Product and UX Issues and Their Resolutions" -Section "Lessons learned"
    $headers = @("Issue", "Observed problem", "Resolution")
    $rows = @(
        @("Public chat leakage", "Shared URL exposed saved chats to other users", "Introduced browser-scoped anonymous ownership filtering"),
        @("Generic recommendations", "Queries like watches under 5000 produced brand-level answers", "Strengthened prompts, added category clarification, pushed model-specific output"),
        @("Slow first responses", "Fresh research paid for multiple AI/retrieval costs", "Hybrid fast-path routing, leaner transcripts, candidate tuning, short-lived cache"),
        @("Vague chat titles", "Auto-titles were not useful in the sidebar", "Moved to one smarter title generated after the first answer"),
        @("Cluttered UI", "Duplicate controls and poor comparison formatting reduced clarity", "Redesigned the interface, simplified controls, replaced tables with compare blocks")
    )
    Add-Table -Slide $slide -Left 24 -Top 92 -Width 912 -Height 346 -Headers $headers -Rows $rows -HeaderFontSize 11 -BodyFontSize 10 | Out-Null
    Add-BulletList -Slide $slide -Left 36 -Top 452 -Width 888 -Height 48 -Items @(
        "The final user experience is the result of iterative correction, not just initial implementation."
    ) -FontSize 14 -Color $Colors.AccentSoft | Out-Null

    $slide = Add-SlideBase -Presentation $presentation -Title "Final Feature Set and Review Readiness" -Section "Outcome"
    $headers = @("Capability group", "Delivered features")
    $rows = @(
        @("Core AI", "Conversational shopping assistant, follow-up support, Gemini synthesis, India-focused outputs"),
        @("Retrieval", "YouTube review search, transcript-backed reasoning, parallel transcript extraction, source dedupe, caching"),
        @("Streaming UX", "SSE response streaming, live status updates, source chips, incremental rendering"),
        @("Sessions", "Saved chats, smart titles, rename/delete, sidebar revisit flow"),
        @("Privacy", "Browser-scoped session isolation with no cross-user leakage"),
        @("Deployment", "GitHub repo, Render frontend/backend, Postgres persistence, health checks"),
        @("UI polish", "Dark minimal design, collapsible sidebar, centered landing page, keyboard-first interaction")
    )
    Add-Table -Slide $slide -Left 60 -Top 96 -Width 840 -Height 300 -Headers $headers -Rows $rows -HeaderFontSize 12 -BodyFontSize 11 | Out-Null
    Add-BulletList -Slide $slide -Left 60 -Top 410 -Width 840 -Height 92 -Items @(
        "Final result: a publicly deployed, evidence-grounded AI shopping assistant with real engineering depth across retrieval, AI orchestration, UX, privacy, persistence, and deployment.",
        "The system is ready for project review because it demonstrates both product thinking and end-to-end implementation rigor."
    ) -FontSize 15 -Color $Colors.Text | Out-Null

    $presentation.SaveAs($OutputPptxPath)
    $presentation.SaveAs($OutputPdfPath, 32)
}
finally {
    if ($presentation) {
        $presentation.Close()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) | Out-Null
    }

    if ($powerPoint) {
        $powerPoint.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) | Out-Null
    }

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Get-Item $OutputPptxPath, $OutputPdfPath | Select-Object FullName, Length, LastWriteTime
