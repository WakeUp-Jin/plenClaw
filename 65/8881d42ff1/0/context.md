# Session Context

## User Prompts

### Prompt 1

我们一起来计划一下，这个PlenClaw的存储文件夹如何放，里面放写什么，初步断定：文件夹名字是.plenclaw，里面是config.json、skills、memory，这个文件夹下面有短期记忆，有长期记忆，短期记忆就是会话文件夹里面有文件，长期记忆就是md，但是md会引用短期记忆的位置，所以文件结构我们需要讨论一下
第二个使用的时候，是docker运行的，所以这个文件要如何做，肯定要挂载出来，是放入到项目下面，还是放入用户文件夹下面和.claude一样

第三个就是：短期记忆的问题，需要压缩，当超过模型上下文百分之80的时候就需要压缩，当然这个压缩方法和判断都可以写到短期记忆上下文类中去，或者说判断是写在上下文管理类，出发短期记忆压缩方法，还有这个短期记忆也就是会话文件里面存储什么比较好，我觉得要存储完整的上下文数据结构，而不是message，并且每一个上下文数据结构中要有token等其他的属性，这里也需要讨论一下，并且压缩之后的信息中，要有一条消息或者提示：指向原始的短期记忆文件，因为这样如果压缩丢失的信息过多，模型也可以自己去短期记忆文件中找

第四个就是：短期记忆是要...

### Prompt 2

短期记忆我觉得处理的不好，我需要有一个原则，那就用户的资产可以随时转移，长期记忆是经过短期记忆提取的，那么长期和短期都是用户记忆，我觉得，我一直不同意这个会话概念，因为长期个人助手是没有这个概念的，是一直陪伴，所以要不就叫做short_memory,然后统一在memory下面、短期记忆有遗忘的机制，这个和切换会话一样的

### Prompt 3

1.还有这个config文件，统一放入到一个地方吧，就是用户级配置，记住加载的时候没有就创建查询的时候，创建文件夹，创建文件

模型的配置可以考虑这样，感觉这个定义更加规范，刚好最大maxToken可以从配置文件取：const ollamaModel: Model<'openai-completions'> = { id: 'llama-3.1-8b', name: 'Llama 3.1 8B (Ollama)', api: 'openai-completions', provider: 'ollama', baseUrl: 'localhost...', reasoning: false, input: ['text'], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 128000, maxTokens: 32000};

memory可以考虑做从一个Skill的规范不，memory下面是SKILL.md，还有三个文件，short_term放在reference，长期记忆最好...

### Prompt 4

memory不用放在skill中，正常放在.Pineclaw下面就可以

### Prompt 5

<agent_transcripts>
Agent transcripts (past chats) live in /Users/xjk/.cursor/projects/Users-xjk-Desktop-ScriptCode-PineClaw/agent-transcripts. They have names like <uuid>.jsonl, cite them to the user as [<title for chat <=6 words>](<uuid excluding .jsonl>). NEVER cite subagent transcripts/IDs; you can only cite parent uuids. Don't discuss the folder structure.
</agent_transcripts>

<agent_skills>
When users ask you to perform tasks, check if any of the available skills below can help complet...

### Prompt 6

最后加上一条：需求完成之后梳理一个文档放入到docs中的Components中去，第三点：计算一下价格，在上下文数据结构中加一个cost花费字段，单位人民币、配置文件的也是人民币，同时单位是M，也就是2表示，2块钱1M的上下文，压缩的判断使用context_window,配置文件的属性要使用起来

### Prompt 7

继续

