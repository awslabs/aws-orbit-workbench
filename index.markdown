---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: default
carousel:
  - image: home/athenaBeta.jpeg
    text: random text 1

  - image: home/transport.jpeg
    text: |
      random text 2

  - image: home/coffee.jpeg
    text: |
      random text 3
---
{% include navigation.html %}


Trying Carousel
{% include carousel.html height="50" unit="%" duration="7" %}
