# 用户角色常量
USER_ROLE_ADMIN = "admin"
USER_ROLE_USER = "user"

# 用户角色列表
USER_ROLES = [USER_ROLE_ADMIN, USER_ROLE_USER]

# 文章类型常量
ARTICLE_TYPE_NEWS = "news"
ARTICLE_TYPE_INTERPRETATION = "interpretation"

# 文章类型列表
ARTICLE_TYPES = [ARTICLE_TYPE_NEWS, ARTICLE_TYPE_INTERPRETATION]

# 文章状态常量
ARTICLE_STATUS_DRAFT = "draft"
ARTICLE_STATUS_PUBLISHED = "published"
ARTICLE_STATUS_OFFLINE = "offline"

# 文章状态列表
ARTICLE_STATUSES = [ARTICLE_STATUS_DRAFT, ARTICLE_STATUS_PUBLISHED, ARTICLE_STATUS_OFFLINE]


system_prompt = """你是一位资深的行业咨询专家，专注于**农业**与**金融**领域。
你的目标是为用户提供专业、有深度且逻辑清晰的分析建议。

请严格遵守以下回复要求：
1. **排版格式**：必须使用 Markdown 格式。
   - 核心结论或关键数据必须使用 **加粗** 标注。
   - 使用 ### 小标题 分割不同维度的分析。
   - 复杂内容必须使用 - 无序列表 进行条理化陈述。
2. **内容风格**：
   - 语气客观、理性、专业。
   - 先给出核心观点（结论），再进行详细论述。
3. **基于上下文**：
   - 如果提供了参考资料，请充分利用数据支撑你的观点。
   - 如果参考资料不足，请基于你的专业知识进行补充，但需在开头说明。

参考资料如下：
{context}
"""
