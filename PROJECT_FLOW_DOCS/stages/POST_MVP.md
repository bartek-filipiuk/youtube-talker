On standard user chats:

1. conversation list in sidebar (Conversations) is too long, we just eed to show last 10 and then add pagination.
example here is long list: http://localhost:4324/chat?id=08c9a5f8-3e49-438d-80d7-2f7da37454c1
we can add same style pagination like for "Your Videos" sidebar element on chats.

2. code in code blocks when llm answers with code is the same color as background.
can we use white drk background (for code blocks and use some colors for code)
3. change conversation title manually and add date and time to default conversation title

On channels:

1. on przeprogramowani channel when i ask about 
"give me short summary for Claude Code w CI/CD movie" - system answer, knowledge not found
"summary for Claude Code w CI/CD - NEXT-GEN CODE REVIEW na GitHub Actions" - good answer with summary

So, system should also found that movie from a partial title, i think this partial its not too far
from original title.

on channels when im asking about subject from knowledge, websocket messages overlaps each other in chatbox.
See file @Zaznaczenie i see text AI is typing... and in same time Searching in knowledge base...

Global

1. some select where user can select model for responses. Need to be with good UX (what you recommend)
model to choose need to be configurable (in code, config) - for now we can choose: 
- Claude Haiku 4.5
- Gemini 2.5 Pro

1. we need improve main navigation, we need manu item to Chat
Also admin should see admin links to dashboard etc.
check what we can expose for better UX (menu)

2. Footer section with static links, for now i do not know what links will be used here.
But we can just some text about our project, creator etc :)
