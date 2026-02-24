# Create your models here.
from django.db import IntegrityError, models


class Cat(models.Model):
    # ok, I think we need at least some length limit for a name
    # 200 should be pretty generous
    #
    # NOTE: name is not required to be unique here
    name = models.CharField(max_length=200)
    experience = models.PositiveIntegerField()
    # we will validate the breed using the api anyway
    # but I checked and the longest breed name seems to be 20-character-long
    breed = models.CharField(max_length=50)
    salary = models.PositiveIntegerField()

    def __str__(self):
        return self.name


class Mission(models.Model):
    # cat may be optional, but I don't think we can delete a cat while
    # they're still assigned to the mission
    #
    # that would be wrong ...
    cat = models.ForeignKey(Cat, on_delete=models.PROTECT, null=True)
    complete = models.BooleanField()

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        # TODO:
        # I wish I knew how to open a transaction here, try to
        # save a new mission, check if cats don't have more than three missions
        # here and if they have, do a rollback
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.cat is not None:
            raise IntegrityError("can't delete a mission with assigned cat")
        super().delete(*args, **kwargs)


class Target(models.Model):
    # NOTE: the same as with cats, name is not require to be unique here.
    # we differentiate them by id
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=200)
    notes = models.TextField()
    complete = models.BooleanField()

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        old_t = Target.objects.get(pk=self.id)
        if self.notes != old_t.notes and (
            self.complete or self.mission.complete
        ):
            raise IntegrityError("can't update notes after completion")

        # go through all targets on linked mission
        # to discover if the mission should be completed
        for t in self.mission.target_set.all():
            # target is us, check if just completed
            # if completed, skip to the next target
            # if not, give up
            if t.id == self.id:
                if not self.complete:
                    break
                else:
                    continue
            # if not completed, give up
            if not t.complete:
                break
        else:
            # if couldn't find uncompleted target to break on, we're done!!
            #
            # yep, Python can use `else` on `for` loops
            #
            # I have no idea how many people find that readable, and whether
            # I should put this into test assesment, but here it is
            #
            # I'm not sure if I'd like to see such code, but I couldn't resist
            # the temptation, so it's up to code reviewer to decide ^^'
            self.mission.complete = True
            self.mission.save()
        super().save(*args, **kwargs)
