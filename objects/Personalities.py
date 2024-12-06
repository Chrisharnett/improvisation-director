import random

from data.PersonalityAttributes import getDescriptions
from decimal import Decimal

class Personality:
    def __init__(self, description=None, weight=.5,  **attributes):
        # Set default values or take provided ones
        defaultAttributes = {
            "Creativity": 5,
            "Complexity": 5,
            "Energy": 5,
            "Interaction": 5,
            "Traditionality": 5,
            "Rhythmic Freedom": 5,
            "Tonal Preference": 5,
            "Adaptability": 5
        }
        # Update defaults with any provided attributes
        defaultAttributes.update(attributes)
        self.__attributes = defaultAttributes
        self.__description = description
        self.__weight = weight

    @property
    def description(self):
        return self.__description

    @description.setter
    def description(self, description):
        self.__description = description

    @property
    def weight(self):
        return self.__weight

    @weight.setter
    def weight(self, weight):
        self.__weight = weight

    def updatePersonality(self, personalityUpdates):
        descriptionUpdate = personalityUpdates.get('description')
        attributesUpdate = personalityUpdates.get('attributes')
        if descriptionUpdate:
            self.description = descriptionUpdate
        if attributesUpdate:
            for attributeName, attributeValue in attributesUpdate.items():
                if attributeName in self.attributes:
                    self.attributes[attributeName] = attributeValue
        return

    def updateAttribute(self, attribute, value):
        if attribute in self.attributes:
            self.attributes[attribute] = round(max(0, min(10, value)), 2)  # Keep score between 0-10
        else:
            print(f"Attribute {attribute} not found.")

    @property
    def attributes(self):
        return self.__attributes

    def incrementAttribute(self, attribute, amount):
        if attribute in self.attributes:
            self.attributes[attribute] = round(max(0, min(10, self.attributes[attribute] + (amount * self.weight))), 2)
        else:
            print(f"Attribute {attribute} not found.")

    def personalityString(self):
        return f"{self.description if self.description else 'Not Set Yet'}. Attributes -  {self.attributeString()}"

    def attributeString(self):
        return ', '.join(f"{k}: {v}" for k, v in self.attributes.items())

    def attributeNames(self):
        return', '.join(f"{k}" for k, v in self.attributes.items())

    def personalityAttributesContext(self, context='performer'):
        contextList = []
        for attr, value in self.attributes.items():
            desc = next((d["description"] for d in getDescriptions(context) if d["name"] == attr), 'No description available')
            contextList.append(f"{attr} ({value}): {desc}")
        return ".".join(contextList)

    def attributeObject(self):
        attributeObject = ""
        for k, v in self.attributes.items():
            if len(attributeObject) > 0:
                attributeObject += ', '
            value = random.randint(0, 10)
            attributeObject += "{'name': " + k + ", {'value': " + str(value) + '}'
        return attributeObject

    def to_dict(self):
        return {
            "description": self.__description,
            "attributes": self.__attributes
        }

    def to_decimalDict(self):
        decimalAttributes = {k: Decimal(str(v)) for k, v in self.attributes.items()}
        return {
            "description": self.__description,
            "attributes": decimalAttributes,
        }

class PerformerPersonality(Personality):
    def __init__(self, musicalKnowledge=5, **attributes):
        weight = 0.7
        super().__init__(weight=weight, **attributes)
        self.attributes["Musical Knowledge"] = musicalKnowledge

    def personalityAttributesContext(self):
        return (f"A Performer's personality attributes are: {super().personalityAttributesContext(context='performer')}"
               "Your response be in the following format: {'description': 'A 10 word description of the personality',"
               "'attributes':  " + super().attributeObject() + '}')

class LLMPersonality(Personality):
    def __init__(self, promptLength=5, focusOnInteraction=5, abstractness=5, **attributes):
        weight = 1
        super().__init__(weight=weight, **attributes)
        self.attributes["Prompt Length"] = promptLength
        self.attributes["Focus on Interaction"] = focusOnInteraction
        self.attributes['Abstractness'] = abstractness

    def personalityAttributesContext(self):
        return f"An LLM's personality attributes are: {super().personalityAttributesContext(context='llm')}." \
               "Your response be in the following format: {'description': 'A 10 word description of the personality'," \
               "'attributes':  " + super().attributeObject() + '}'


