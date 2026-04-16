param(
    [string]$TemplatePath = "docs\\AST05_working_copy.docx",
    [string]$OutputDocx = "docs\\VL2025260506155_AST05_COMPLETED.docx",
    [string]$OutputPdf = "docs\\VL2025260506155_AST05_COMPLETED.pdf"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TemplateFullPath = Join-Path $ProjectRoot $TemplatePath
$OutputDocxFullPath = Join-Path $ProjectRoot $OutputDocx
$OutputPdfFullPath = Join-Path $ProjectRoot $OutputPdf

$RepoUrl = "https://github.com/chathurvedivanga/agentic-ai-personal-shopper"
$LiveUrl = "https://ai-shopping-partner-web.onrender.com/"
$ApiUrl = "https://agentic-ai-personal-shopper-api.onrender.com/api/health"

$Screenshots = @(
    @{ Path = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120536.png"; Caption = "Landing page of AI Shopping Partner before interaction." },
    @{ Path = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120552.png"; Caption = "Prompt composition for an Indian-market recommendation query." },
    @{ Path = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120602.png"; Caption = "Live streaming state while the system searches YouTube and prepares a response." },
    @{ Path = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 120703.png"; Caption = "Source transparency layer showing the YouTube review links used during answer generation." },
    @{ Path = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 121207.png"; Caption = "Recommendation output with verdict and quick-compare format." },
    @{ Path = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 121235.png"; Caption = "Detailed recommendation output with product-level specificity and INR pricing." },
    @{ Path = "C:\Users\RAM\OneDrive\Pictures\Screenshots\Screenshot 2026-04-09 121253.png"; Caption = "Final response with attached YouTube evidence chips for traceable decision support." }
)

$script:HeadingEntries = New-Object System.Collections.ArrayList
$script:FigureEntries = New-Object System.Collections.ArrayList
$script:TableEntries = New-Object System.Collections.ArrayList
$script:TableCounter = 0
$script:FigureCounter = 0

function Add-HeadingEntry {
    param(
        [string]$Number,
        [string]$Title,
        [int]$Level,
        [int]$Start
    )

    [void]$script:HeadingEntries.Add([PSCustomObject]@{
        Number = $Number
        Title  = $Title
        Level  = $Level
        Start  = $Start
    })
}

function Add-FigureEntry {
    param(
        [string]$Caption,
        [int]$Start
    )

    $script:FigureCounter++
    [void]$script:FigureEntries.Add([PSCustomObject]@{
        Number  = $script:FigureCounter
        Caption = $Caption
        Start   = $Start
    })
}

function Add-TableEntry {
    param(
        [string]$Caption,
        [int]$Start
    )

    $script:TableCounter++
    [void]$script:TableEntries.Add([PSCustomObject]@{
        Number  = $script:TableCounter
        Caption = $Caption
        Start   = $Start
    })
}

function Set-TextFormatting {
    param(
        $Selection,
        [string]$Style = "Normal",
        [string]$FontName = "Times New Roman",
        [int]$FontSize = 12,
        [bool]$Bold = $false,
        [int]$Alignment = 3
    )

    $Selection.Style = $Style
    $Selection.Font.Name = $FontName
    $Selection.Font.Size = $FontSize
    $Selection.Font.Bold = $(if ($Bold) { 1 } else { 0 })
    $Selection.ParagraphFormat.Alignment = $Alignment
    $Selection.ParagraphFormat.SpaceAfter = 6
    $Selection.ParagraphFormat.SpaceBefore = 0
    $Selection.ParagraphFormat.LineSpacingRule = 0
    $Selection.ParagraphFormat.LineSpacing = 18
}

function Write-Paragraph {
    param(
        $Selection,
        [string]$Text,
        [string]$Style = "Normal",
        [int]$FontSize = 12,
        [bool]$Bold = $false,
        [int]$Alignment = 3
    )

    Set-TextFormatting -Selection $Selection -Style $Style -FontSize $FontSize -Bold $Bold -Alignment $Alignment
    $Selection.TypeText($Text)
    $Selection.TypeParagraph()
}

function Write-Bullets {
    param(
        $Selection,
        [string[]]$Items,
        [int]$FontSize = 12
    )

    Set-TextFormatting -Selection $Selection -Style "Normal" -FontSize $FontSize -Bold $false -Alignment 0
    $Selection.Range.ListFormat.ApplyBulletDefault()
    foreach ($item in $Items) {
        $Selection.TypeText($item)
        $Selection.TypeParagraph()
    }
    $Selection.Range.ListFormat.RemoveNumbers()
    $Selection.TypeParagraph()
}

function Write-Heading {
    param(
        $Selection,
        [string]$Number,
        [string]$Title,
        [int]$Level = 1
    )

    $style = if ($Level -eq 1) { "Heading 1" } elseif ($Level -eq 2) { "Heading 2" } else { "Heading 3" }
    $fontSize = if ($Level -eq 1) { 16 } elseif ($Level -eq 2) { 14 } else { 13 }
    $start = $Selection.Range.Start
    Write-Paragraph -Selection $Selection -Text ("$Number $Title".Trim()) -Style $style -FontSize $fontSize -Bold $true -Alignment 0
    Add-HeadingEntry -Number $Number -Title $Title -Level $Level -Start $start
}

function Insert-PageBreak {
    param($Selection)
    $Selection.InsertBreak(7)
}

function Write-Table {
    param(
        $Document,
        $Selection,
        [string]$Caption,
        [string[]]$Headers,
        [object[][]]$Rows,
        [int[]]$ColumnWidths = @()
    )

    $captionStart = $Selection.Range.Start
    Write-Paragraph -Selection $Selection -Text ("Table {0}: {1}" -f ($script:TableCounter + 1), $Caption) -Style "Normal" -FontSize 11 -Bold $true -Alignment 1
    Add-TableEntry -Caption $Caption -Start $captionStart

    $table = $Document.Tables.Add($Selection.Range, $Rows.Count + 1, $Headers.Count)
    $table.Style = "Table Grid"
    $table.Borders.Enable = 1
    $table.Range.Font.Name = "Times New Roman"
    $table.Range.Font.Size = 10

    if ($ColumnWidths.Count -eq $Headers.Count) {
        for ($i = 0; $i -lt $Headers.Count; $i++) {
            $table.Columns.Item($i + 1).Width = $ColumnWidths[$i]
        }
    }

    for ($c = 0; $c -lt $Headers.Count; $c++) {
        $table.Cell(1, $c + 1).Range.Text = $Headers[$c]
        $table.Cell(1, $c + 1).Range.Bold = 1
        $table.Cell(1, $c + 1).Shading.BackgroundPatternColor = 15132390
    }

    for ($r = 0; $r -lt $Rows.Count; $r++) {
        for ($c = 0; $c -lt $Headers.Count; $c++) {
            $table.Cell($r + 2, $c + 1).Range.Text = [string]$Rows[$r][$c]
        }
    }

    $Selection.SetRange($table.Range.End, $table.Range.End)
    $Selection.TypeParagraph()
    $Selection.TypeParagraph()
}

function Insert-Figure {
    param(
        $Selection,
        [string]$ImagePath,
        [string]$Caption,
        [double]$MaxWidth = 430
    )

    Set-TextFormatting -Selection $Selection -Style "Normal" -FontSize 12 -Bold $false -Alignment 1
    $shape = $Selection.InlineShapes.AddPicture($ImagePath)
    if ($shape.Width -gt $MaxWidth) {
        $shape.LockAspectRatio = -1
        $shape.Width = $MaxWidth
    }
    $Selection.TypeParagraph()
    $captionStart = $Selection.Range.Start
    Write-Paragraph -Selection $Selection -Text ("Figure {0}: {1}" -f ($script:FigureCounter + 1), $Caption) -Style "Normal" -FontSize 11 -Bold $true -Alignment 1
    Add-FigureEntry -Caption $Caption -Start $captionStart
    $Selection.TypeParagraph()
}

function Insert-CodeBlock {
    param(
        $Document,
        $Selection,
        [string]$Title,
        [string]$Code
    )

    Write-Paragraph -Selection $Selection -Text $Title -Style "Heading 3" -FontSize 12 -Bold $true -Alignment 0
    $table = $Document.Tables.Add($Selection.Range, 1, 1)
    $table.Style = "Table Grid"
    $table.Borders.Enable = 1
    $table.Cell(1,1).Range.Text = $Code
    $table.Cell(1,1).Range.Font.Name = "Consolas"
    $table.Cell(1,1).Range.Font.Size = 9
    $table.Cell(1,1).Shading.BackgroundPatternColor = 15987699
    $Selection.SetRange($table.Range.End, $table.Range.End)
    $Selection.TypeParagraph()
    $Selection.TypeParagraph()
}

function Fill-IndexTable {
    param(
        $Table,
        [object[]]$Entries,
        [scriptblock]$LabelScript,
        [scriptblock]$PageScript
    )

    $maxRows = $Table.Rows.Count - 1
    for ($i = 1; $i -le $maxRows; $i++) {
        $Table.Cell($i + 1, 1).Range.Text = ""
        $Table.Cell($i + 1, 2).Range.Text = ""
        if ($Table.Columns.Count -ge 3) {
            $Table.Cell($i + 1, 3).Range.Text = ""
        }
    }

    for ($i = 0; $i -lt [Math]::Min($Entries.Count, $maxRows); $i++) {
        $entry = $Entries[$i]
        $Table.Cell($i + 2, 1).Range.Text = & $LabelScript $entry
        $Table.Cell($i + 2, 2).Range.Text = $entry.Title
        if ($Table.Columns.Count -ge 3) {
            $Table.Cell($i + 2, 3).Range.Text = [string](& $PageScript $entry)
        }
    }
}

function Get-PageNo {
    param(
        $Document,
        [int]$Start
    )

    return [int]$Document.Range($Start, $Start).Information(3)
}

if (Test-Path $OutputDocxFullPath) {
    Remove-Item $OutputDocxFullPath -Force
}

Copy-Item $TemplateFullPath $OutputDocxFullPath -Force

$word = $null
$doc = $null

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $doc = $word.Documents.Open($OutputDocxFullPath)
    $selection = $word.Selection

    $page2 = $doc.GoTo(1, 1, 2)
    $deleteRange = $doc.Range($page2.Start, $doc.Content.End - 1)
    $deleteRange.Delete()
    $selection.SetRange($page2.Start, $page2.Start)

    Write-Paragraph -Selection $selection -Text "Table of Contents" -Style "Heading 1" -FontSize 16 -Bold $true -Alignment 0
    $tocTable = $doc.Tables.Add($selection.Range, 40, 3)
    $tocTable.Style = "Table Grid"
    $tocTable.Borders.Enable = 1
    $tocTable.Range.Font.Name = "Times New Roman"
    $tocTable.Range.Font.Size = 10
    $tocTable.Columns.Item(1).Width = 70
    $tocTable.Columns.Item(2).Width = 330
    $tocTable.Columns.Item(3).Width = 60
    $tocTable.Cell(1,1).Range.Text = "Section"
    $tocTable.Cell(1,2).Range.Text = "Title"
    $tocTable.Cell(1,3).Range.Text = "Page"
    $tocTable.Rows.Item(1).Range.Bold = 1
    $selection.SetRange($tocTable.Range.End, $tocTable.Range.End)
    Insert-PageBreak -Selection $selection

    $abstractStart = $selection.Range.Start
    Write-Heading -Selection $selection -Number "" -Title "ABSTRACT" -Level 1
    Write-Paragraph -Selection $selection -Text "AI Shopping Partner is a full-stack conversational shopping assistant developed to reduce the time, fragmentation, and uncertainty involved in online product research. The system allows a user to ask natural-language shopping questions such as budget recommendations, comparisons, and follow-up queries, and then responds with a synthesized verdict grounded in YouTube review evidence. The project combines a React and Vite frontend, a Flask backend, Google Gemini for answer synthesis, YouTube transcript retrieval for evidence extraction, and Server-Sent Events for live response streaming. The design objective was to create a research assistant that feels like a modern AI chatbot while still remaining evidence-aware, modular, and deployment-ready." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Paragraph -Selection $selection -Text "The backend follows a modular architecture with separate layers for routing, Gemini orchestration, YouTube search and transcript extraction, and persistence. The system intelligently decides whether a new prompt requires fresh YouTube research or can be answered from prior context. When new research is needed, it searches YouTube for relevant review videos, extracts transcripts in parallel using ThreadPoolExecutor, and streams the synthesized recommendation to the frontend in real time using SSE. The application further supports persistent saved chats, smart chat titling, session rename/delete operations, browser-private chat isolation, and production deployment to Render with Postgres-backed persistence." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Bullets -Selection $selection -Items @(
        "Primary contribution: an evidence-grounded AI shopping assistant focused on the Indian market.",
        "Technical highlights: hybrid tool routing, transcript-backed reasoning, live streaming UX, and browser-private session persistence.",
        "Final outcome: a publicly deployed web application that demonstrates full-stack engineering, AI integration, retrieval design, UX refinement, and deployment readiness."
    ) -FontSize 11
    Insert-PageBreak -Selection $selection

    $figListStart = $selection.Range.Start
    Write-Heading -Selection $selection -Number "" -Title "LIST OF FIGURES" -Level 1
    $figureListTable = $doc.Tables.Add($selection.Range, 18, 3)
    $figureListTable.Style = "Table Grid"
    $figureListTable.Borders.Enable = 1
    $figureListTable.Range.Font.Name = "Times New Roman"
    $figureListTable.Range.Font.Size = 10
    $figureListTable.Columns.Item(1).Width = 60
    $figureListTable.Columns.Item(2).Width = 360
    $figureListTable.Columns.Item(3).Width = 60
    $figureListTable.Cell(1,1).Range.Text = "Fig. No."
    $figureListTable.Cell(1,2).Range.Text = "Name of the Figure"
    $figureListTable.Cell(1,3).Range.Text = "Page No."
    $figureListTable.Rows.Item(1).Range.Bold = 1
    $selection.SetRange($figureListTable.Range.End, $figureListTable.Range.End)
    Insert-PageBreak -Selection $selection

    $abbrStart = $selection.Range.Start
    Write-Heading -Selection $selection -Number "" -Title "LIST OF ABBREVIATIONS" -Level 1
    Write-Table -Document $doc -Selection $selection -Caption "Key abbreviations used in the report" -Headers @("Sr. No.", "Abbreviation", "Expanded Form") -Rows @(
        @("1", "AI", "Artificial Intelligence"),
        @("2", "LLM", "Large Language Model"),
        @("3", "API", "Application Programming Interface"),
        @("4", "SSE", "Server-Sent Events"),
        @("5", "UI", "User Interface"),
        @("6", "UX", "User Experience"),
        @("7", "DB", "Database"),
        @("8", "ORM", "Object Relational Mapping"),
        @("9", "INR", "Indian Rupee"),
        @("10", "HTTP", "Hypertext Transfer Protocol")
    ) -ColumnWidths @(55, 110, 305)
    Insert-PageBreak -Selection $selection

    $tableListStart = $selection.Range.Start
    Write-Heading -Selection $selection -Number "" -Title "LIST OF TABLES" -Level 1
    $tableListTable = $doc.Tables.Add($selection.Range, 16, 3)
    $tableListTable.Style = "Table Grid"
    $tableListTable.Borders.Enable = 1
    $tableListTable.Range.Font.Name = "Times New Roman"
    $tableListTable.Range.Font.Size = 10
    $tableListTable.Columns.Item(1).Width = 60
    $tableListTable.Columns.Item(2).Width = 360
    $tableListTable.Columns.Item(3).Width = 60
    $tableListTable.Cell(1,1).Range.Text = "Table No."
    $tableListTable.Cell(1,2).Range.Text = "Name of the Table"
    $tableListTable.Cell(1,3).Range.Text = "Page No."
    $tableListTable.Rows.Item(1).Range.Bold = 1
    $selection.SetRange($tableListTable.Range.End, $tableListTable.Range.End)
    Insert-PageBreak -Selection $selection

    Write-Heading -Selection $selection -Number "CHAPTER 1" -Title "INTRODUCTION" -Level 1
    Write-Heading -Selection $selection -Number "1.1" -Title "SYSTEM OVERVIEW" -Level 2
    Write-Paragraph -Selection $selection -Text "AI Shopping Partner is a conversational web application designed to support product discovery, recommendation, comparison, and follow-up decision making through a single continuous chat interface. Unlike a conventional search workflow in which the user manually opens multiple review videos, compares features, and remembers earlier findings, the proposed system centralizes the activity into one evidence-grounded research assistant. The user enters a product query or budget constraint, the backend decides whether fresh review evidence is needed, retrieves YouTube reviews when appropriate, extracts transcript content in parallel, and asks Gemini to synthesize a buyer-friendly recommendation. The synthesized answer is streamed back to the browser in real time, and the chat is saved for future continuation." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Bullets -Selection $selection -Items @(
        "User-facing role: conversational personal shopping assistant for the Indian market.",
        "Evidence source: YouTube review videos and their transcripts, not manual copy-paste by the user.",
        "AI role: synthesize verdicts, shortlist options, compare alternatives, and answer follow-up questions.",
        "Persistence layer: session-based storage that allows users to return to prior shopping discussions.",
        "Deployment goal: public accessibility with privacy preserved per browser session."
    ) -FontSize 11
    Write-Table -Document $doc -Selection $selection -Caption "System overview summary" -Headers @("Aspect", "Description") -Rows @(
        @("Primary problem", "Online shopping research is fragmented, repetitive, and difficult to consolidate."),
        @("Primary users", "Students, professionals, and general buyers evaluating products under a budget."),
        @("Input format", "Natural-language prompts, comparisons, and follow-up questions."),
        @("Output format", "Verdicts, quick comparisons, watch-outs, and source-backed responses."),
        @("Evidence mode", "Transcript-backed YouTube review synthesis with UI source chips."),
        @("Interaction model", "Chat-based interface with session history and revisit support.")
    ) -ColumnWidths @(120, 360)

    Write-Heading -Selection $selection -Number "1.2" -Title "OBJECTIVE" -Level 2
    Write-Bullets -Selection $selection -Items @(
        "To build a full-stack web application that behaves like a modern AI chat assistant while remaining grounded in product-review evidence.",
        "To reduce the manual effort required to compare products across multiple YouTube videos and review sources.",
        "To support both first-time research and follow-up questions inside the same conversation thread.",
        "To provide real-time streaming feedback so the user sees the assistant researching and drafting the answer live.",
        "To make the system modular, deployable, and maintainable through clear separation of routing, retrieval, AI logic, and storage."
    ) -FontSize 11
    Write-Table -Document $doc -Selection $selection -Caption "Project objectives classified by engineering focus" -Headers @("Objective type", "Target outcome") -Rows @(
        @("Functional", "Deliver recommendations, comparisons, follow-up handling, and evidence visibility."),
        @("Architectural", "Maintain modular separation of frontend, backend, retrieval, and storage."),
        @("Experience", "Provide a dark, professional, low-friction interface with live feedback."),
        @("Operational", "Deploy publicly using GitHub, Render, and Postgres."),
        @("Reliability", "Handle transcript failures, model errors, and cross-user privacy issues gracefully.")
    ) -ColumnWidths @(130, 350)

    Write-Heading -Selection $selection -Number "1.3" -Title "APPLICATIONS" -Level 2
    Write-Bullets -Selection $selection -Items @(
        "Budget-conscious product research for phones, laptops, smartwatches, appliances, and accessories.",
        "Shortlisting products before purchase by combining review evidence into one structured verdict.",
        "Follow-up comparison tasks such as battery life, performance, thermal behavior, and software trade-offs.",
        "Academic demonstration of full-stack AI engineering, conversational UX, and evidence-driven recommendation design.",
        "Prototype foundation for future extensions such as authentication, richer product cards, or multi-source evidence aggregation."
    ) -FontSize 11

    Write-Heading -Selection $selection -Number "1.4" -Title "LIMITATIONS" -Level 2
    Write-Bullets -Selection $selection -Items @(
        "The system currently uses YouTube as the primary evidence layer and does not yet aggregate official e-commerce platform data.",
        "Cross-device identity is not supported because the privacy model is intentionally browser-scoped without login.",
        "Public deployment on free-tier infrastructure may experience cold-start delay and Gemini quota limits.",
        "Some videos may not expose transcripts, which can force the assistant to fall back to metadata and stable knowledge.",
        "Recommendations depend on the quality and recency of the retrieved review ecosystem for the queried category."
    ) -FontSize 11

    Insert-PageBreak -Selection $selection

    Write-Heading -Selection $selection -Number "CHAPTER 2" -Title "SYSTEM ANALYSIS" -Level 1
    Write-Heading -Selection $selection -Number "2.1" -Title "EXISTING SYSTEM" -Level 2
    Write-Paragraph -Selection $selection -Text "The existing shopping research workflow for most users is highly fragmented. A buyer typically opens multiple YouTube review videos, reads article reviews, compares prices manually, and tries to mentally remember the differences between several products. Conventional chatbot systems may provide quick suggestions, but they often return generic brand-level advice without clearly citing where the recommendation came from. In practice, this results in three major inefficiencies: information overload, weak traceability, and poor continuity across sessions." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Table -Document $doc -Selection $selection -Caption "Existing shopping research challenges" -Headers @("Existing approach", "Observed problem", "Impact on the user") -Rows @(
        @("Manual video review", "User must watch multiple long-form videos independently", "High time consumption"),
        @("Standard search engine flow", "Information is spread across tabs and platforms", "Poor synthesis and difficult comparison"),
        @("Generic AI chatbot", "Answers may be broad and uncited", "Low trust and weak shopping usefulness"),
        @("No persistent context", "Research is lost between sessions", "Repeated effort for follow-up questions")
    ) -ColumnWidths @(130, 200, 150)

    Write-Heading -Selection $selection -Number "2.2" -Title "PROPOSED SYSTEM" -Level 2
    Write-Paragraph -Selection $selection -Text "The proposed system addresses these weaknesses by combining a conversational interface with a research pipeline that actively retrieves YouTube review evidence, extracts transcript content in parallel, and uses Gemini to synthesize a structured answer. Instead of forcing the user to inspect every source manually, the application converts the evidence into a shortlist, verdict, watch-outs, and comparison output. Saved sessions and smart titles make the research reusable, while browser-private ownership ensures that public users cannot view each other's chats. The proposed system therefore acts both as an AI assistant and as a research organizer." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Bullets -Selection $selection -Items @(
        "Evidence-aware recommendation rather than brand-only or hallucinated advice.",
        "Hybrid routing that avoids unnecessary retrieval for follow-up questions.",
        "Parallel transcript extraction to reduce latency during fresh research.",
        "Live streaming feedback to keep the user informed during long-running operations.",
        "Persistent chat state with rename, delete, and revisit support."
    ) -FontSize 11

    Write-Heading -Selection $selection -Number "2.2.1" -Title "BENEFITS OF PROPOSED SYSTEM" -Level 3
    Write-Table -Document $doc -Selection $selection -Caption "Benefits of the proposed system" -Headers @("Benefit area", "Improvement delivered by the proposed system") -Rows @(
        @("Decision quality", "Recommendations are grounded in actual review evidence and structured into buyer-friendly verdicts."),
        @("Time efficiency", "Parallel retrieval and summarized comparisons reduce manual research effort."),
        @("Continuity", "Saved sessions allow users to return to old buying decisions without starting from zero."),
        @("Transparency", "YouTube source chips expose what videos informed the response."),
        @("Usability", "The interface behaves like a modern AI assistant rather than a traditional form-based system."),
        @("Deployment readiness", "The system is already version-controlled, hosted, and backed by production persistence.")
    ) -ColumnWidths @(135, 345)

    Insert-PageBreak -Selection $selection

    Write-Heading -Selection $selection -Number "CHAPTER 3" -Title "REQUIREMENT SPECIFICATION" -Level 1
    Write-Heading -Selection $selection -Number "3.1" -Title "HARDWARE REQUIREMENTS" -Level 2
    Write-Paragraph -Selection $selection -Text "The hardware requirements for this project are modest for normal development and end-user operation because the computationally intensive language processing is handled by the Gemini API. However, a stable development environment, browser support, and uninterrupted network access are essential for successful execution of the application." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Table -Document $doc -Selection $selection -Caption "Hardware requirements for development and usage" -Headers @("Category", "Minimum requirement", "Recommended requirement") -Rows @(
        @("Processor", "Dual-core 64-bit CPU", "Quad-core modern CPU"),
        @("RAM", "8 GB", "16 GB or above"),
        @("Storage", "2 GB free disk space", "5 GB free disk space"),
        @("Display", "1366 x 768 resolution", "1920 x 1080 resolution"),
        @("Network", "Stable broadband internet", "High-speed broadband with low latency"),
        @("Input devices", "Standard keyboard and mouse", "Standard keyboard and mouse / laptop touchpad")
    ) -ColumnWidths @(120, 180, 180)

    Write-Heading -Selection $selection -Number "3.2" -Title "SOFTWARE REQUIREMENTS" -Level 2
    Write-Paragraph -Selection $selection -Text "The software stack for AI Shopping Partner was selected to support rapid full-stack development, modular backend design, browser-based user interaction, and public deployment. The requirements below include both the local development environment and the production stack used on Render." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Table -Document $doc -Selection $selection -Caption "Software and platform requirements" -Headers @("Software / service", "Version / type", "Role in the system") -Rows @(
        @("Operating System", "Windows 10/11, macOS, or Linux", "Local development and testing"),
        @("Python", "3.13.x", "Backend runtime"),
        @("Node.js", ">= 20 and < 23", "Frontend build and Vite runtime"),
        @("Flask", "3.1.0", "REST API and streaming endpoint"),
        @("google-generativeai", "0.8.4", "Gemini model integration"),
        @("youtube-search-python", "1.6.6", "YouTube search without official data API"),
        @("youtube-transcript-api", "1.2.4", "Transcript retrieval"),
        @("SQLAlchemy", "2.0.46", "Persistence abstraction"),
        @("React + Vite", "React 18 + Vite 5", "Frontend SPA and developer tooling"),
        @("Tailwind CSS", "3.4.15", "Styling system"),
        @("Render", "Managed cloud platform", "Frontend, backend, and Postgres deployment"),
        @("GitHub", "Remote source repository", "Version control and deployment source")
    ) -ColumnWidths @(150, 120, 210)

    Insert-PageBreak -Selection $selection

    Write-Heading -Selection $selection -Number "CHAPTER 4" -Title "SYSTEM DESIGN SPECIFICATION" -Level 1
    Write-Heading -Selection $selection -Number "4.1" -Title "SYSTEM ARCHITECTURE" -Level 2
    Write-Paragraph -Selection $selection -Text "The architecture of AI Shopping Partner follows a layered full-stack pattern. The React frontend handles the user interface, composer, chat rendering, session list, and SSE event consumption. The Flask backend exposes REST endpoints for sessions and a streaming endpoint for chat. Within the backend, app.py coordinates HTTP requests and streaming, agent.py manages Gemini orchestration and title generation, scraper.py handles YouTube search and transcript extraction, and storage.py manages session and message persistence. The production deployment uses Render for hosting and Postgres for durable storage. This modular decomposition isolates concerns and made it possible to evolve the project incrementally without rewriting the entire system." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Table -Document $doc -Selection $selection -Caption "High-level architecture flow" -Headers @("Layer", "Inputs", "Processing", "Outputs") -Rows @(
        @("React frontend", "Prompt text, active session, browser events", "Fetch API calls, SSE parsing, state updates, rendering", "User-visible chat experience"),
        @("Flask API", "HTTP requests from frontend", "Validation, session lookup, streaming orchestration", "Session data and SSE event stream"),
        @("Gemini orchestration", "User prompt, history, research context", "Tool routing, synthesis, title generation", "Final recommendation text"),
        @("YouTube retrieval", "Search query and category intent", "Video search, transcript extraction, dedupe, truncation", "Evidence bundle with sources"),
        @("Persistence", "Sessions, messages, sources, owner IDs", "Create, update, load, rename, delete, privacy filtering", "Durable chat state")
    ) -ColumnWidths @(110, 120, 170, 130)

    Write-Heading -Selection $selection -Number "4.2" -Title "DETAILED DESIGN" -Level 2
    Write-Table -Document $doc -Selection $selection -Caption "Detailed backend component design" -Headers @("Component", "Detailed responsibility") -Rows @(
        @("app.py", "Initializes Flask and CORS, maintains secure viewer cookie, exposes health check, session CRUD routes, and the streaming chat endpoint."),
        @("agent.py", "Defines the shopping system prompt, candidate Gemini models, hybrid routing logic, chat title generation, and streamed answer generation."),
        @("scraper.py", "Normalizes shopping queries, biases them toward Indian-market review intent, runs YouTube search, and extracts transcripts in parallel."),
        @("storage.py", "Creates and migrates session/message schema, scopes data by owner_id, and supports both SQLite and Postgres."),
        @("App.jsx", "Maintains client-side state for sessions, messages, active streaming response, sidebar visibility, and send/stop interactions."),
        @("lib/sse.js", "Parses the raw SSE stream into structured events consumed by the React state layer.")
    ) -ColumnWidths @(120, 410)
    Write-Table -Document $doc -Selection $selection -Caption "Core API endpoints" -Headers @("Endpoint", "Method", "Purpose") -Rows @(
        @("/api/health", "GET", "Health validation for deployment and monitoring"),
        @("/api/sessions", "GET", "Fetch all sessions for the current browser owner"),
        @("/api/sessions/<id>", "GET", "Load a specific chat with all messages"),
        @("/api/sessions/<id>", "PATCH", "Rename a session"),
        @("/api/sessions/<id>", "DELETE", "Delete a session"),
        @("/api/chat", "POST", "Create/resume a session and stream the assistant response")
    ) -ColumnWidths @(170, 70, 290)

    Write-Heading -Selection $selection -Number "4.3" -Title "DATABASE DESIGN" -Level 2
    Write-Paragraph -Selection $selection -Text "The persistence layer is intentionally simple but production-appropriate. It revolves around two main entities: sessions and messages. Each session belongs to a browser-scoped owner and stores metadata such as title, timestamps, and title readiness. Each message belongs to a session and stores role, content, serialized sources, and timestamp. This design is sufficient to support chat replay, session listing, source-aware rendering, and privacy filtering." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Table -Document $doc -Selection $selection -Caption "Database schema design" -Headers @("Table", "Important fields", "Purpose") -Rows @(
        @("sessions", "id, owner_id, title, title_ready, created_at, updated_at", "Stores chat metadata and browser ownership."),
        @("messages", "id, session_id, role, content, sources_json, created_at", "Stores user and assistant messages with optional source payloads.")
    ) -ColumnWidths @(100, 240, 190)
    Write-Bullets -Selection $selection -Items @(
        "owner_id is the key field that prevents public users from seeing one another's saved chats.",
        "sources_json preserves the YouTube source metadata required by the frontend chip display.",
        "The schema runs on SQLite locally and Postgres in production without changing the higher-level API."
    ) -FontSize 11

    Insert-PageBreak -Selection $selection

    Write-Heading -Selection $selection -Number "CHAPTER 5" -Title "RESULT AND CONCLUSION" -Level 1
    Write-Heading -Selection $selection -Number "5.1" -Title "RESULT" -Level 2
    Write-Paragraph -Selection $selection -Text "The final system successfully satisfies the original project goal of building a deployable, conversational, evidence-grounded shopping assistant. The application accepts product queries, autonomously researches YouTube review content, synthesizes concise product verdicts, supports follow-up clarification, preserves sessions, and streams the output live in a professional interface. The screenshots below demonstrate the main user journey from landing, prompt input, active retrieval, source visibility, and final recommendation output." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Insert-Figure -Selection $selection -ImagePath $Screenshots[0].Path -Caption $Screenshots[0].Caption -MaxWidth 420
    Insert-Figure -Selection $selection -ImagePath $Screenshots[1].Path -Caption $Screenshots[1].Caption -MaxWidth 420
    Insert-Figure -Selection $selection -ImagePath $Screenshots[2].Path -Caption $Screenshots[2].Caption -MaxWidth 420
    Insert-Figure -Selection $selection -ImagePath $Screenshots[3].Path -Caption $Screenshots[3].Caption -MaxWidth 420
    Insert-Figure -Selection $selection -ImagePath $Screenshots[4].Path -Caption $Screenshots[4].Caption -MaxWidth 420
    Insert-Figure -Selection $selection -ImagePath $Screenshots[5].Path -Caption $Screenshots[5].Caption -MaxWidth 420
    Insert-Figure -Selection $selection -ImagePath $Screenshots[6].Path -Caption $Screenshots[6].Caption -MaxWidth 420
    Write-Table -Document $doc -Selection $selection -Caption "Observed outcome summary" -Headers @("Evaluation area", "Observed result") -Rows @(
        @("User interface", "Professional dark theme, collapsible sidebar, keyboard-friendly prompt composer, and source-aware chat bubbles."),
        @("AI behavior", "Supports recommendations, comparisons, follow-ups, and smart auto-titling."),
        @("Evidence handling", "Uses YouTube review search and transcript-backed synthesis with graceful fallback."),
        @("Streaming UX", "Shows real-time status updates and chunked answer rendering through SSE."),
        @("Persistence", "Supports saved sessions, rename/delete, and revisit flow."),
        @("Privacy", "Public users do not see each other's chats due to owner-scoped storage.")
    ) -ColumnWidths @(140, 390)

    Write-Heading -Selection $selection -Number "5.2" -Title "CONCLUSION" -Level 2
    Write-Paragraph -Selection $selection -Text "AI Shopping Partner began as an assignment-driven full-stack project and matured into a production-style application that demonstrates real engineering depth. The project successfully integrates frontend design, backend orchestration, streaming communication, AI reasoning, retrieval engineering, persistence, privacy, and cloud deployment into one cohesive system. Beyond meeting the initial functional requirements, the project also resolved several non-trivial real-world issues such as dependency mismatches, YouTube search breakage, model compatibility, public chat leakage, quota constraints, and UI clutter. The final application therefore stands not only as a working shopping assistant, but also as a strong case study in iterative full-stack product engineering." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Write-Bullets -Selection $selection -Items @(
        "The system demonstrates that an AI assistant can remain conversational without giving up evidence awareness.",
        "The modular backend and persistent session model make the project maintainable and extensible.",
        "The deployment to Render with Postgres elevates the project from a local demo to a publicly usable web application.",
        "Future work could add user authentication, richer product cards, broader source aggregation, and more robust quota management."
    ) -FontSize 11

    Insert-PageBreak -Selection $selection

    Write-Heading -Selection $selection -Number "CHAPTER 6" -Title "APPENDICES" -Level 1
    Write-Heading -Selection $selection -Number "6.1" -Title "APPENDIX 1 - SAMPLE SOURCE CODE" -Level 2
    Write-Paragraph -Selection $selection -Text "The following excerpts illustrate representative implementation logic from the final system. They are included to demonstrate the actual coding style, the streaming mechanism, the parallel transcript pipeline, and the frontend SSE parser." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    Insert-CodeBlock -Document $doc -Selection $selection -Title "Sample 1: SSE event formatting in server/app.py" -Code @"
def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
"@
    Insert-CodeBlock -Document $doc -Selection $selection -Title "Sample 2: Parallel transcript extraction in server/scraper.py" -Code @"
def fetch_transcripts_parallel(videos, max_workers=5, target_count=4):
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_fetch_video_transcript, video): index
            for index, video in enumerate(videos)
        }
        for future in as_completed(future_map):
            item = future.result()
            if item is None:
                continue
"@
    Insert-CodeBlock -Document $doc -Selection $selection -Title "Sample 3: Client-side SSE parsing in client/src/lib/sse.js" -Code @"
export function consumeSseEvents(buffer) {
  const normalized = buffer.replace(/\r\n/g, '\n');
  const blocks = normalized.split('\n\n');
  const remainder = blocks.pop() ?? '';
  const events = blocks.map((block) => parseEventBlock(block)).filter(Boolean);
  return { events, remainder };
}
"@
    Insert-CodeBlock -Document $doc -Selection $selection -Title "Sample 4: Session-aware fetch in client/src/App.jsx" -Code @"
async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...options
  });
  return response.json();
}
"@

    Write-Heading -Selection $selection -Number "6.2" -Title "APPENDIX 2 - SCREEN SHOTS / OUTPUTS" -Level 2
    Write-Paragraph -Selection $selection -Text "This appendix consolidates key UI screenshots from the final deployed system. These figures were selected to show the full lifecycle of interaction: landing, prompt entry, live retrieval, evidence surfacing, and final product recommendation output." -Style "Normal" -FontSize 12 -Bold $false -Alignment 3
    foreach ($shot in $Screenshots) {
        Insert-Figure -Selection $selection -ImagePath $shot.Path -Caption $shot.Caption -MaxWidth 430
    }

    Write-Heading -Selection $selection -Number "6.3" -Title "REPOSITORY URL" -Level 2
    Write-Bullets -Selection $selection -Items @(
        "GitHub Repository: $RepoUrl",
        "Live Frontend URL: $LiveUrl",
        "Backend Health Endpoint: $ApiUrl"
    ) -FontSize 11

    Insert-PageBreak -Selection $selection

    Write-Heading -Selection $selection -Number "CHAPTER 7" -Title "REFERENCES" -Level 1
    Write-Heading -Selection $selection -Number "7.1" -Title "LIST OF JOURNALS" -Level 2
    Write-Bullets -Selection $selection -Items @(
        "[1] Gediminas Adomavicius and Alexander Tuzhilin, 'Toward the Next Generation of Recommender Systems: A Survey of the State-of-the-Art and Possible Extensions,' IEEE Transactions on Knowledge and Data Engineering, 2005.",
        "[2] Dietmar Jannach, Pearl Pu, Francesco Ricci, and Markus Zanker, 'Recommender Systems: Beyond Matrix Completion,' Communications of the ACM, 2021.",
        "[3] Chin-Yew Lin and others, 'Conversational Recommender Systems: A Survey of the State of the Art and Future Directions,' ACM Computing Surveys, 2023.",
        "[4] Patrick Lewis et al., 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,' Advances in Neural Information Processing Systems, 2020."
    ) -FontSize 11

    Write-Heading -Selection $selection -Number "7.2" -Title "LIST OF WEBSITES (URLs)" -Level 2
    Write-Bullets -Selection $selection -Items @(
        "[5] Flask Documentation - https://flask.palletsprojects.com/",
        "[6] React Documentation - https://react.dev/",
        "[7] Vite Documentation - https://vite.dev/",
        "[8] Tailwind CSS Documentation - https://tailwindcss.com/docs/",
        "[9] Google Gemini API Documentation - https://ai.google.dev/gemini-api/docs",
        "[10] youtube-transcript-api - https://pypi.org/project/youtube-transcript-api/",
        "[11] youtube-search-python - https://pypi.org/project/youtube-search-python/",
        "[12] Render Documentation - https://render.com/docs",
        "[13] GitHub Docs - https://docs.github.com/"
    ) -FontSize 11

    Write-Heading -Selection $selection -Number "7.3" -Title "LIST OF BOOKS" -Level 2
    Write-Bullets -Selection $selection -Items @(
        "[14] Miguel Grinberg, Flask Web Development, O'Reilly Media, 2018.",
        "[15] Stoyan Stefanov, React Up and Running, O'Reilly Media, 2021.",
        "[16] Martin Kleppmann, Designing Data-Intensive Applications, O'Reilly Media, 2017.",
        "[17] Chip Huyen, AI Engineering: Building Applications with Foundation Models, O'Reilly Media, 2025."
    ) -FontSize 11

    $tocEntries = New-Object System.Collections.ArrayList
    [void]$tocEntries.Add([PSCustomObject]@{ Number=""; Title="ABSTRACT"; Level=1; Start=$abstractStart })
    [void]$tocEntries.Add([PSCustomObject]@{ Number=""; Title="LIST OF FIGURES"; Level=1; Start=$figListStart })
    [void]$tocEntries.Add([PSCustomObject]@{ Number=""; Title="LIST OF ABBREVIATIONS"; Level=1; Start=$abbrStart })
    [void]$tocEntries.Add([PSCustomObject]@{ Number=""; Title="LIST OF TABLES"; Level=1; Start=$tableListStart })
    foreach ($entry in $script:HeadingEntries) {
        if ($entry.Title -in @("ABSTRACT", "LIST OF FIGURES", "LIST OF ABBREVIATIONS", "LIST OF TABLES")) {
            continue
        }
        [void]$tocEntries.Add($entry)
    }

    $doc.Repaginate()

    for ($i = 0; $i -lt $tocEntries.Count; $i++) {
        if ($i + 2 -gt $tocTable.Rows.Count) {
            break
        }
        $entry = $tocEntries[$i]
        $label = if ($entry.Number) { $entry.Number } else { "-" }
        $indent = if ($entry.Level -gt 1) { "    " * ($entry.Level - 1) } else { "" }
        $tocTable.Cell($i + 2, 1).Range.Text = $label
        $tocTable.Cell($i + 2, 2).Range.Text = $indent + $entry.Title
        $tocTable.Cell($i + 2, 3).Range.Text = [string](Get-PageNo -Document $doc -Start $entry.Start)
    }

    for ($i = 0; $i -lt $script:FigureEntries.Count; $i++) {
        if ($i + 2 -gt $figureListTable.Rows.Count) {
            break
        }
        $entry = $script:FigureEntries[$i]
        $figureListTable.Cell($i + 2, 1).Range.Text = [string]$entry.Number
        $figureListTable.Cell($i + 2, 2).Range.Text = $entry.Caption
        $figureListTable.Cell($i + 2, 3).Range.Text = [string](Get-PageNo -Document $doc -Start $entry.Start)
    }

    for ($i = 0; $i -lt $script:TableEntries.Count; $i++) {
        if ($i + 2 -gt $tableListTable.Rows.Count) {
            break
        }
        $entry = $script:TableEntries[$i]
        $tableListTable.Cell($i + 2, 1).Range.Text = [string]$entry.Number
        $tableListTable.Cell($i + 2, 2).Range.Text = $entry.Caption
        $tableListTable.Cell($i + 2, 3).Range.Text = [string](Get-PageNo -Document $doc -Start $entry.Start)
    }

    $null = $doc.Fields.Update()
    $doc.Save()
}
finally {
    if ($doc) {
        $doc.Close()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
    }

    if ($word) {
        $word.Quit()
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Get-Item $OutputDocxFullPath | Select-Object FullName, Length, LastWriteTime
