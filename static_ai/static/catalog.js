export const skillInfo = {
  web_search: [
    "Web search",
    "globe",
    "Find useful sources across the public web.",
    "Research",
  ],
  web_read: [
    "Read the web",
    "book",
    "Turn public pages into useful, cited context.",
    "Research",
  ],
  file_create: [
    "Documents & files",
    "file",
    "Create PDF, Word, Markdown, CSV, JSON and more.",
    "Create",
  ],
  file_read: [
    "Read your files",
    "folder",
    "Use text files and PDFs in your conversations.",
    "Files",
  ],
  file_list: [
    "Find your files",
    "search",
    "Find work you have created in a conversation.",
    "Files",
  ],
  mesh_create: [
    "3D shapes",
    "cube",
    "Build real OBJ geometry: cubes, spheres and cylinders.",
    "Create",
  ],
  media_generate: [
    "Generative media",
    "sparkles",
    "Make images, videos and 3D models with a connected provider.",
    "Create",
  ],
  plan_update: [
    "Make a plan",
    "check-square",
    "Break a goal into steps and keep progress visible.",
    "Organize",
  ],
  agent_delegate: [
    "Specialist agents",
    "bolt",
    "Bring in a focused researcher, writer, coder or planner.",
    "Agents",
  ],
  shopping_compare: [
    "Compare offers",
    "bag",
    "Compare price, shipping and known tax. You complete checkout.",
    "Organize",
  ],
  calendar_create: [
    "Calendar events",
    "calendar",
    "Prepare an event file to import into your calendar.",
    "Organize",
  ],
  email_draft: [
    "Email drafts",
    "mail",
    "Write an email draft you can review and send yourself.",
    "Organize",
  ],
  table_analyze: [
    "Understand a CSV",
    "chart",
    "Count rows and calculate numeric column summaries.",
    "Research",
  ],
};
export const ideas = [
  {
    title: "Find the right thing, for less.",
    category: "Research",
    art: "research",
    icon: "bag",
    subtitle: "Compare options. Keep the good ones.",
    footer: "Web research + comparison",
    prompt:
      "Help me compare products and find the best value. First ask what I want to buy, my country, requirements and total budget. Use current sources and include shipping and unknown taxes.",
  },
  {
    title: "Make that idea a real thing.",
    category: "Create",
    art: "create",
    icon: "sparkles",
    subtitle: "From a blank page to something yours.",
    footer: "Images, documents & 3D",
    prompt:
      "Help me turn an idea into a finished creative project. Ask what I want to make, the format, style and budget, then create the deliverable using available tools.",
  },
  {
    title: "A little more life. Less admin.",
    category: "Organize",
    art: "plan",
    icon: "calendar",
    subtitle: "Give the details somewhere to go.",
    footer: "Plans + everyday tasks",
    prompt:
      "Help me organize my week. Ask about my priorities, available time and timezone, then make a realistic plan with optional calendar event files.",
  },
];
export const creationTypes = [
  {
    id: "document",
    name: "Document",
    icon: "file",
    label: "What are we writing?",
    placeholder: "A concise project proposal for a community garden…",
    note: "Create a downloadable document in your chosen format.",
    examples: [
      "A project proposal",
      "A polished meeting brief",
      "A monthly budget spreadsheet",
    ],
    formats: [
      ["md", "Markdown"],
      ["pdf", "PDF"],
      ["docx", "Word document"],
      ["csv", "CSV spreadsheet"],
      ["html", "HTML"],
      ["json", "JSON"],
      ["txt", "Plain text"],
    ],
  },
  {
    id: "image",
    name: "Image",
    icon: "image",
    label: "Describe your image",
    placeholder:
      "A sculptural glass object, soft lavender light, editorial photography…",
    note: "Uses your configured image provider. Static asks for approval before a paid generation.",
    examples: [
      "A soft, abstract wallpaper",
      "An editorial product concept",
      "A friendly app illustration",
    ],
  },
  {
    id: "video",
    name: "Video",
    icon: "video",
    label: "Describe the scene",
    placeholder:
      "A slow camera move through a sunlit studio, warm light, 5 seconds…",
    note: "Uses your configured video provider. Duration and resolution follow its saved profile.",
    examples: [
      "A cinematic opening shot",
      "A calming nature loop",
      "A product launch storyboard",
    ],
  },
  {
    id: "3d",
    name: "3D model",
    icon: "cube",
    label: "What would you like to build?",
    placeholder: "A sphere with 24 segments, exported as an OBJ file…",
    note: "Basic OBJ shapes run locally. Generative 3D needs a configured media model and approval.",
    examples: [
      "A simple sphere in OBJ",
      "A low-poly cylinder",
      "A geometric product concept",
    ],
    formats: [
      ["procedural", "Local geometry (OBJ)"],
      ["generative", "Generative 3D (provider)"],
    ],
  },
  {
    id: "everyday",
    name: "Everyday",
    icon: "calendar",
    label: "Take one thing off your list",
    placeholder:
      "Draft an email to reschedule a meeting, or prepare a calendar event…",
    note: "Drafts and calendar files stay yours to review, send or import.",
    examples: [
      "Draft a thoughtful follow-up",
      "Make a calendar event file",
      "Plan my week on a budget",
    ],
  },
];
