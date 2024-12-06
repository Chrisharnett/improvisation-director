from dataclasses import dataclass

@dataclass
class AttributeDescription:
    name: str
    scale: str
    performerDescription: str
    llmDescription: str

    def getDescription(self, context='performer'):
        if context == 'performer':
            return self.performerDescription
        elif context == 'llm':
            return self.llmDescription
        else:
            return "No description available"

# Example attribute descriptions
descriptions = [
    AttributeDescription(
        name="Creativity",
        scale="0-10",
        performerDescription="Reflects the performer's preference for taking musical risks, exploring new ideas, and going beyond traditional approaches.",
        llmDescription="Reflects the LLM's ability to generate unique, creative, and unconventional responses or combinations of responses."
    ),
    AttributeDescription(
        name="Complexity",
        scale="0-10",
        performerDescription="Indicates the level of technical intricacy the performer prefers, such as using complex rhythms, harmonic structures, and fast or challenging musical phrases.",
        llmDescription="Indicates the complexity level of the LLM's responses, such as the depth of reasoning, use of sophisticated vocabulary, or complexity in generated solutions."
    ),
    AttributeDescription(
        name="Energy",
        scale="0-10",
        performerDescription="Represents the intensity and dynamism of the performer's playing style. High energy means the performer favors fast, powerful, and driving music, while a lower score might mean more relaxed or mellow playing.",
        llmDescription="Represents the intensity and enthusiasm of the LLM's responses. High energy reflects engaging and enthusiastic communication, while low energy may indicate a more calm and reserved style."
    ),
    AttributeDescription(
        name="Interaction",
        scale="0-10",
        performerDescription="Measures how much the performer engages and interacts with other musicians. High interaction means the performer actively listens and responds to others, while a low score might indicate a preference for playing more independently.",
        llmDescription="Represents the LLM's ability to interact contextually with users' inputs, providing responsive and conversational answers."
    ),
    AttributeDescription(
        name="Traditionality",
        scale="0-10",
        performerDescription="Describes the performer's inclination towards conventional, traditional styles versus more modern or experimental approaches. A high score suggests a preference for classical or well-established styles, whereas a low score indicates openness to avant-garde or unorthodox techniques.",
        llmDescription="Represents the LLM's preference towards providing conventional, well-established answers versus more modern or experimental responses."
    ),
    AttributeDescription(
        name="Rhythmic Freedom",
        scale="0-10",
        performerDescription="Indicates how freely the performer approaches rhythm, such as using rubato or deviating from strict time. A high score means more rhythmic exploration and flexibility, while a low score suggests a preference for keeping precise time.",
        llmDescription="Reflects the LLM's willingness to deviate from expected conversational patterns, generating varied and unpredictable response timings."
    ),
    AttributeDescription(
        name="Tonal Preference",
        scale="0-10",
        performerDescription="Represents the preference for tonal stability. A high score means the performer favors tonal, harmonic music, while a lower score might indicate an interest in atonal or dissonant approaches.",
        llmDescription="Indicates the LLM's preference for generating positive and harmonic responses versus dissonant or critical responses."
    ),
    AttributeDescription(
        name="Adaptability",
        scale="0-10",
        performerDescription="Reflects how easily the performer adapts to changes in the environment, feedback, or other musicians' actions. High adaptability means the performer is comfortable changing style or focus as needed, while low adaptability suggests they prefer to stick with a chosen path.",
        llmDescription="Represents the LLM's ability to adapt to changes in user instructions or new input contexts, providing relevant and flexible responses."
    ),
    AttributeDescription(
        name="Musical Knowledge",
        scale="0-10",
        performerDescription="Represents the performer's familiarity and proficiency with different musical concepts, such as scales, harmonic progressions, and complex time signatures. A high score indicates strong theoretical knowledge and technical proficiency, allowing the performer to comfortably navigate complex musical material.",
        llmDescription="Represents the LLM's proficiency with musical knowledge, such as understanding of musical theory and technical concepts related to music."
    ),
    AttributeDescription(
        name="Focus on Interaction",
        scale="0-10",
        performerDescription="Measures the degree to which the performer interacts and communicates with others during a performance.",
        llmDescription="Reflects the LLM's emphasis on directing performers to indirect. A high score indicates the LLM gives specific directions on who should be playing when and with whom, and shapes the music through changes in instrumentation and instrumet roles. A low score indicates the LLM leaves those decisions to the performers."
    ),
    AttributeDescription(
        name="Abstractness",
        scale="0-10",
        performerDescription="Measures the degree to which the performer enjoys prompts that emphasis non-musical or programmatic ideas.",
        llmDescription="Reflects the LLM's emphasis on directing performers with abstract, non-musical prompts. A low score indicates a preference for clear, understandable and musical directions. For example. Play a blues in Bb in 4/4 at 144 bpm. A high score indicates a preference for abstract, obliques prompts. For example: Play the sound of strawberries, or, Play when you feel right."
    )
]

def getDescriptions(context='performer'):
    return [
        {
            "name": desc.name,
            "scale": desc.scale,
            "description": desc.getDescription(context)
        }
        for desc in descriptions
    ]

